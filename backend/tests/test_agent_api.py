from types import SimpleNamespace

import pytest

from app import retrieval
from app.agent_tools import (
    approve_leave_request,
    query_leave_balance,
    query_my_leave_requests,
    query_pending_approvals,
    submit_leave_request,
)
from app.agent_data import ensure_demo_data
from app.agent_service import PendingActionStore, pending_store
from app.database import SessionLocal
from app.models import (
    ActionEvent,
    AgentAction,
    AppSetting,
    AgentSession,
    Chunk,
    Document,
    Employee,
    LeaveBalance,
    LeaveRequest,
)


@pytest.fixture(autouse=True)
def clean_agent_state():
    db = SessionLocal()
    try:
        db.query(ActionEvent).delete()
        db.query(AgentAction).delete()
        db.query(LeaveRequest).delete()
        db.query(LeaveBalance).delete()
        db.query(Employee).delete()
        db.query(AgentSession).delete()
        db.query(AppSetting).delete()
        db.commit()
        ensure_demo_data(db)
    finally:
        db.close()
    pending_store.clear()
    yield


def _tool_call(call_id: str, name: str, arguments: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _message(content: str | None, tool_calls: list[SimpleNamespace] | None = None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def test_agent_query_leave_balance(client, monkeypatch):
    calls = iter(
        [
            _message(
                None,
                [
                    _tool_call(
                        "call-balance",
                        "query_leave_balance",
                        '{"employee_name": "张三"}',
                    )
                ],
            ),
            _message("张三2026年年假余额为3天。"),
        ]
    )
    monkeypatch.setattr(
        "app.agent_service.call_agent_model",
        lambda messages, tools=None: next(calls),
    )

    resp = client.post(
        "/api/agent/chat",
        json={"message": "张三的年假余额还有多少？", "employee_id": "E001"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"]
    assert "3 天" in data["answer"] or "3天" in data["answer"]
    assert data["pending_action"] is None


def test_query_balance_tool_reports_pending_capacity(client):
    result = query_leave_balance(
        {"employee_name": "张三"},
        employee_id="E001",
        role="employee",
    )
    assert "年假余额 3 天" in result.content
    assert "待审批申请占用 2 天" in result.content
    assert "当前可申请 1 天" in result.content


def test_employee_can_only_query_own_requests(client):
    result = query_my_leave_requests({}, employee_id="E001", role="employee")
    assert "LR-2026-0901" in result.content
    assert "LR-2026-0902" not in result.content


def test_only_manager_can_query_pending_approvals(client):
    result = query_pending_approvals({}, employee_id="M001", role="manager")
    assert "LR-2026-0901" in result.content
    assert "LR-2026-0902" not in result.content

    with pytest.raises(ValueError, match="没有审批权限"):
        query_pending_approvals({}, employee_id="E001", role="employee")


def test_non_approver_cannot_prepare_approval(client):
    with pytest.raises(ValueError, match="没有审批权限"):
        approve_leave_request(
            {"request_id": "LR-2026-0901"},
            employee_id="E001",
            role="employee",
        )


def test_manager_leave_is_approved_by_general_manager(client):
    result = submit_leave_request(
        {
            "employee_name": "李明",
            "leave_type": "年假",
            "start_date": "2026-09-21",
            "end_date": "2026-09-21",
            "days": 1,
            "reason": "个人事务",
        },
        employee_id="M001",
        role="manager",
    )
    assert result.pending_action is not None
    assert result.pending_action.payload["approver_id"] == "G001"
    pending_store.put(result.pending_action, session_id="test-manager-leave")
    request_id, _ = pending_store.confirm(result.pending_action.action_id)
    approvals = query_pending_approvals(
        {}, employee_id="G001", role="manager"
    )
    assert request_id in approvals.content


def test_agent_submit_requires_confirmation_then_confirm(client, monkeypatch):
    submit_args = (
        '{"employee_name": "张三", "leave_type": "年假", '
        '"start_date": "2026-09-10", "end_date": "2026-09-11", '
        '"days": 1, "reason": "家中有事"}'
    )
    calls = iter(
        [
            _message(
                None,
                [
                    _tool_call(
                        "call-submit",
                        "submit_leave_request",
                        submit_args,
                    )
                ],
            ),
            _message("已生成待确认的请假申请，请确认提交。"),
        ]
    )
    monkeypatch.setattr(
        "app.agent_service.call_agent_model",
        lambda messages, tools=None: next(calls),
    )

    resp = client.post(
        "/api/agent/chat",
        json={"message": "帮我请1天年假", "employee_id": "E001"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_action"] is not None
    action_id = data["pending_action"]["action_id"]
    reloaded = PendingActionStore().get(action_id)
    assert reloaded is not None
    assert reloaded.payload["employee_id"] == "E001"

    db = SessionLocal()
    try:
        before_count = db.query(LeaveRequest).count()
        action = (
            db.query(AgentAction)
            .filter(AgentAction.action_id == action_id)
            .first()
        )
        assert action is not None
        assert action.status == "待确认"
    finally:
        db.close()

    confirm = client.post(f"/api/agent/actions/{action_id}/confirm")
    assert confirm.status_code == 200
    body = confirm.json()
    assert body["status"] == "confirmed"
    assert body["request_id"].startswith("LV-")

    db = SessionLocal()
    try:
        assert db.query(LeaveRequest).count() == before_count + 1
        balance = (
            db.query(LeaveBalance)
            .join(Employee, Employee.id == LeaveBalance.employee_id)
            .filter(Employee.employee_id == "E001")
            .first()
        )
        assert balance.used_days == 2
        action = (
            db.query(AgentAction)
            .filter(AgentAction.action_id == action_id)
            .first()
        )
        assert action.status == "已完成"
        assert action.confirmed_at is not None
        assert action.result_json
        event_types = [
            row.event_type
            for row in (
                db.query(ActionEvent)
                .filter(ActionEvent.action_id == action_id)
                .order_by(ActionEvent.created_at.asc())
                .all()
            )
        ]
        assert event_types == ["created", "confirmed", "executed"]
    finally:
        db.close()


def test_agent_submit_insufficient_balance_does_not_write(client, monkeypatch):
    submit_args = (
        '{"employee_name": "张三", "leave_type": "年假", '
        '"start_date": "2026-09-10", "end_date": "2026-09-14", '
        '"days": 5, "reason": "旅行"}'
    )
    calls = iter(
        [
            _message(
                None,
                [
                    _tool_call(
                        "call-submit",
                        "submit_leave_request",
                        submit_args,
                    )
                ],
            ),
            _message("你的年假余额不足，无法提交申请。"),
        ]
    )
    monkeypatch.setattr(
        "app.agent_service.call_agent_model",
        lambda messages, tools=None: next(calls),
    )

    resp = client.post(
        "/api/agent/chat",
        json={"message": "帮我请5天年假", "employee_id": "E001"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_action"] is None

    db = SessionLocal()
    try:
        assert db.query(LeaveRequest).count() == 7
        balance = (
            db.query(LeaveBalance)
            .join(Employee, Employee.id == LeaveBalance.employee_id)
            .filter(Employee.employee_id == "E001")
            .first()
        )
        assert balance.used_days == 2
    finally:
        db.close()


def test_agent_search_knowledge_returns_citations(client, monkeypatch):
    db = SessionLocal()
    try:
        doc = Document(
            doc_id="T-AGENT-001",
            title="年休假操作说明",
            filename="annual.md",
            category="制度类",
            permission="全员",
            owner="人力资源部",
            status="已上传",
            source="测试",
            method="测试",
            update_date="2026-09-01",
            file_path="",
        )
        doc.chunks.append(
            Chunk(
                chunk_index=0,
                heading="申请流程",
                content="年假应提前3个工作日通过 OA 提交，获批后方可休假。",
                char_count=28,
            )
        )
        db.add(doc)
        db.commit()
    finally:
        db.close()
    retrieval.build_index()

    calls = iter(
        [
            _message(
                None,
                [
                    _tool_call(
                        "call-search",
                        "search_knowledge",
                        '{"query": "年假怎么申请"}',
                    )
                ],
            ),
            _message("年假应提前3个工作日提交申请。"),
        ]
    )
    monkeypatch.setattr(
        "app.agent_service.call_agent_model",
        lambda messages, tools=None: next(calls),
    )

    resp = client.post(
        "/api/agent/chat",
        json={"message": "年假怎么申请？", "employee_id": "E001"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(item["doc_id"] == "T-AGENT-001" for item in data["citations"])


def test_agent_cancel_pending_action(client, monkeypatch, as_user):
    as_user("E006")
    submit_args = (
        '{"employee_name": "刘洋", "leave_type": "年假", '
        '"start_date": "2026-09-21", "end_date": "2026-09-25", '
        '"days": 5, "reason": "家庭安排"}'
    )
    calls = iter(
        [
            _message(
                None,
                [
                    _tool_call(
                        "call-submit",
                        "submit_leave_request",
                        submit_args,
                    )
                ],
            ),
            _message("已生成待确认申请，请确认。"),
        ]
    )
    monkeypatch.setattr(
        "app.agent_service.call_agent_model",
        lambda messages, tools=None: next(calls),
    )
    resp = client.post(
        "/api/agent/chat",
        json={"message": "帮我请5天年假", "employee_id": "E006"},
    )
    action_id = resp.json()["pending_action"]["action_id"]

    cancel = client.delete(f"/api/agent/actions/{action_id}")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"

    db = SessionLocal()
    try:
        assert db.query(LeaveRequest).count() == 7
        action = (
            db.query(AgentAction)
            .filter(AgentAction.action_id == action_id)
            .first()
        )
        assert action.status == "已取消"
        event_types = [
            row.event_type
            for row in (
                db.query(ActionEvent)
                .filter(ActionEvent.action_id == action_id)
                .all()
            )
        ]
        assert event_types == ["created", "cancelled"]
    finally:
        db.close()


def test_manager_approves_request_after_confirmation(
    client, monkeypatch, as_user
):
    as_user("M001")
    calls = iter(
        [
            _message(
                None,
                [
                    _tool_call(
                        "call-approve",
                        "approve_leave_request",
                        '{"request_id": "LR-2026-0901"}',
                    )
                ],
            ),
            _message("已准备批准申请，请确认后执行。"),
        ]
    )
    monkeypatch.setattr(
        "app.agent_service.call_agent_model",
        lambda messages, tools=None: next(calls),
    )

    resp = client.post(
        "/api/agent/chat",
        json={"message": "批准 LR-2026-0901", "employee_id": "M001"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending_action"]["tool"] == "approve_leave_request"
    action_id = data["pending_action"]["action_id"]

    db = SessionLocal()
    try:
        request = (
            db.query(LeaveRequest)
            .filter(LeaveRequest.request_id == "LR-2026-0901")
            .first()
        )
        assert request.status == "待审批"
    finally:
        db.close()

    confirm = client.post(f"/api/agent/actions/{action_id}/confirm")
    assert confirm.status_code == 200

    db = SessionLocal()
    try:
        request = (
            db.query(LeaveRequest)
            .filter(LeaveRequest.request_id == "LR-2026-0901")
            .first()
        )
        balance = (
            db.query(LeaveBalance)
            .join(Employee, Employee.id == LeaveBalance.employee_id)
            .filter(Employee.employee_id == "E001")
            .first()
        )
        action = (
            db.query(AgentAction)
            .filter(AgentAction.action_id == action_id)
            .first()
        )
        assert request.status == "已批准"
        assert request.approved_at is not None
        assert balance.used_days == 4
        assert action.status == "已完成"
    finally:
        db.close()

    duplicate = client.post(f"/api/agent/actions/{action_id}/confirm")
    assert duplicate.status_code == 409


def test_manager_rejects_request_without_changing_balance(
    client, monkeypatch, as_user
):
    as_user("M002")
    calls = iter(
        [
            _message(
                None,
                [
                    _tool_call(
                        "call-reject",
                        "reject_leave_request",
                        '{"request_id": "LR-2026-0902", '
                        '"reason": "项目上线关键期"}',
                    )
                ],
            ),
            _message("已准备拒绝申请，请确认后执行。"),
        ]
    )
    monkeypatch.setattr(
        "app.agent_service.call_agent_model",
        lambda messages, tools=None: next(calls),
    )

    resp = client.post(
        "/api/agent/chat",
        json={"message": "拒绝 LR-2026-0902", "employee_id": "M002"},
    )
    action_id = resp.json()["pending_action"]["action_id"]
    confirm = client.post(f"/api/agent/actions/{action_id}/confirm")
    assert confirm.status_code == 200

    db = SessionLocal()
    try:
        request = (
            db.query(LeaveRequest)
            .filter(LeaveRequest.request_id == "LR-2026-0902")
            .first()
        )
        balance = (
            db.query(LeaveBalance)
            .join(Employee, Employee.id == LeaveBalance.employee_id)
            .filter(Employee.employee_id == "E007")
            .first()
        )
        assert request.status == "已拒绝"
        assert request.reject_reason == "项目上线关键期"
        assert request.rejected_at is not None
        assert balance.used_days == 4
    finally:
        db.close()


def test_task_center_endpoints_support_approval_flow(client, as_user):
    as_user("A001")
    employees = client.get("/api/agent/employees")
    assert employees.status_code == 200
    assert len(employees.json()) == 20

    as_user("E001")
    mine = client.get(
        "/api/agent/leave-requests",
        params={"status": "待审批"},
    )
    assert mine.status_code == 200
    assert mine.json()
    assert all(item["employee_id"] == "E001" for item in mine.json())

    as_user("M001")
    approvals = client.get(
        "/api/agent/approvals",
    )
    assert approvals.status_code == 200
    assert any(
        item["request_id"] == "LR-2026-0901"
        for item in approvals.json()
    )

    as_user("E001")
    forbidden = client.get(
        "/api/agent/approvals",
    )
    assert forbidden.status_code == 403

    as_user("M001")
    prepared = client.post(
        "/api/agent/leave-requests/LR-2026-0901/approve",
    )
    assert prepared.status_code == 200
    action_id = prepared.json()["action_id"]
    assert prepared.json()["tool"] == "approve_leave_request"

    confirmed = client.post(f"/api/agent/actions/{action_id}/confirm")
    assert confirmed.status_code == 200

    audit = client.get("/api/agent/actions")
    assert audit.status_code == 200
    assert any(
        item["action_id"] == action_id for item in audit.json()
    )
    detail = client.get(f"/api/agent/actions/{action_id}")
    assert detail.status_code == 200
    assert [
        event["event_type"] for event in detail.json()["events"]
    ] == ["created", "confirmed", "executed"]

    db = SessionLocal()
    try:
        request = (
            db.query(LeaveRequest)
            .filter(LeaveRequest.request_id == "LR-2026-0901")
            .first()
        )
        assert request.status == "已批准"
    finally:
        db.close()


def test_demo_reset_requires_admin_and_restores_counts(client, as_user):
    as_user("E001")
    forbidden = client.post("/api/agent/demo/reset")
    assert forbidden.status_code == 403

    as_user("A001")
    response = client.post("/api/agent/demo/reset")
    assert response.status_code == 200
    assert response.json() == {
        "employees": 20,
        "balances": 20,
        "leave_requests": 7,
    }
