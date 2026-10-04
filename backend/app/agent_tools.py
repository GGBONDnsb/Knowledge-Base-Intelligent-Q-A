from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import retrieval
from app.agent_audit import record_event
from app.agent_data import DEMO_YEAR
from app.database import SessionLocal
from app.models import AgentAction, Employee, LeaveBalance, LeaveRequest

VALID_LEAVE_TYPES = {"年假"}


@dataclass
class PendingAction:
    action_id: str
    tool: str
    employee_id: str
    summary: str
    payload: dict
    created_at: str

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "tool": self.tool,
            "employee_id": self.employee_id,
            "summary": self.summary,
            "payload": self.payload,
            "created_at": self.created_at,
        }


@dataclass
class ToolResult:
    content: str
    pending_action: PendingAction | None = None
    citations: list[dict] = field(default_factory=list)


TOOL_SPECS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "query_leave_balance",
            "description": "查询指定员工的年假余额。余额、已用天数必须以本工具返回结果为准，不能编造。",
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_name": {
                        "type": "string",
                        "description": "员工姓名，例如张三",
                    },
                    "year": {
                        "type": "integer",
                        "description": "年度，缺省为当前年度",
                    },
                },
                "required": ["employee_name"],
            },
        },
    },
      {
        "type": "function",
        "function": {
            "name": "query_my_leave_requests",
            "description": "查询当前员工自己的请假申请。只能返回当前会话员工的数据，不能查询其他员工。",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["待审批", "已批准", "已拒绝", "已取消"],
                        "description": "可选的状态筛选",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_pending_approvals",
            "description": "查询当前主管需要审批的请假申请。只能返回 approver_id 指向当前主管的待审批申请。",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "approve_leave_request",
            "description": "准备批准一条请假申请。该操作是写操作，只会生成待确认动作，用户确认后才真正批准。",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {
                        "type": "string",
                        "description": "请假申请编号",
                    }
                },
                "required": ["request_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reject_leave_request",
            "description": "准备拒绝一条请假申请。该操作是写操作，只会生成待确认动作，用户确认后才真正拒绝。",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_id": {
                        "type": "string",
                        "description": "请假申请编号",
                    },
                    "reason": {
                        "type": "string",
                        "description": "拒绝原因，不能为空",
                    },
                },
                "required": ["request_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_pending_actions",
            "description": "查询当前员工尚待确认的写操作草稿，例如刚生成但尚未确认的请假申请。",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "revise_leave_request_draft",
            "description": "修改当前员工尚未确认的请假申请草稿。用户说改成、换成、调整刚才的申请时使用。只修改待确认动作，不提交业务申请。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_id": {
                        "type": "string",
                        "description": "待修改的动作编号",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "新的开始日期 YYYY-MM-DD，可选",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "新的结束日期 YYYY-MM-DD，可选",
                    },
                    "days": {
                        "type": "number",
                        "description": "新的申请天数，可选",
                    },
                    "reason": {
                        "type": "string",
                        "description": "新的请假事由，可选",
                    },
                },
                "required": ["action_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "搜索企业知识库制度、产品和技术文档，用于回答年假制度、流程等知识问题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "自然语言检索词",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_leave_request",
            "description": "为当前员工准备一条年假申请。该操作是写操作，只会生成待确认动作，用户确认后才真正提交。",
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_name": {
                        "type": "string",
                        "description": "员工姓名，必须与当前会话员工一致",
                    },
                    "leave_type": {
                        "type": "string",
                        "enum": ["年假"],
                        "description": "假别，当前版本仅支持年假",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "开始日期，格式 YYYY-MM-DD",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "结束日期，格式 YYYY-MM-DD",
                    },
                    "days": {
                        "type": "number",
                        "description": "申请天数，按 0.5 天为单位",
                    },
                    "reason": {
                        "type": "string",
                        "description": "请假事由",
                    },
                },
                "required": [
                    "employee_name",
                    "leave_type",
                    "start_date",
                    "end_date",
                    "days",
                    "reason",
                ],
            },
        },
    },
]


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("日期格式应为 YYYY-MM-DD") from exc


def _weekday_count(start: date, end: date) -> float:
    if end < start:
        raise ValueError("结束日期不能早于开始日期")
    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5:
            count += 1
        current += date.resolution
    return float(count)


def _resolve_employee(
    db: Session,
    employee_id: str | None = None,
    employee_name: str | None = None,
) -> Employee:
    query = db.query(Employee)
    if employee_id:
        query = query.filter(Employee.employee_id == employee_id)
    elif employee_name:
        query = query.filter(Employee.name == employee_name)
    else:
        raise ValueError("缺少员工标识")
    employee = query.first()
    if employee is None:
        raise ValueError("未找到对应员工，请使用正确的员工姓名")
    return employee


def _get_balance(db: Session, employee: Employee, year: int) -> LeaveBalance:
    balance = (
        db.query(LeaveBalance)
        .filter(
            LeaveBalance.employee_id == employee.id,
            LeaveBalance.year == year,
        )
        .first()
    )
    if balance is None:
        raise ValueError(f"{employee.name} {year} 年没有年假余额记录")
    return balance


def _pending_days(
    db: Session,
    employee: Employee,
    leave_type: str = "年假",
) -> float:
    value = (
        db.query(func.coalesce(func.sum(LeaveRequest.days), 0.0))
        .filter(
            LeaveRequest.employee_id == employee.id,
            LeaveRequest.leave_type == leave_type,
            LeaveRequest.status == "待审批",
            LeaveRequest.start_date.like(f"{DEMO_YEAR}-%"),
        )
        .scalar()
    )
    return float(value or 0)


def query_leave_balance(
    args: dict[str, Any], employee_id: str, role: str
) -> ToolResult:
    employee_name = str(args.get("employee_name", "")).strip()
    year = int(args.get("year") or DEMO_YEAR)
    db = SessionLocal()
    try:
        employee = _resolve_employee(db, employee_name=employee_name)
        balance = _get_balance(db, employee, year)
        remaining = balance.total_days - balance.used_days
        pending = _pending_days(db, employee)
        available = remaining - pending
        text = (
            f"{employee.name}（{employee.employee_id}）{year} 年年假余额 "
            f"{remaining:g} 天（总额 {balance.total_days:g} 天，"
            f"已使用 {balance.used_days:g} 天）"
        )
        if pending:
            text += f"；待审批申请占用 {pending:g} 天，当前可申请 {available:g} 天"
    finally:
        db.close()
    return ToolResult(content=text)


def _serialize_leave_request(
    request: LeaveRequest, employee: Employee
) -> dict[str, Any]:
    submitted = (
        request.submitted_at.strftime("%Y-%m-%d %H:%M")
        if request.submitted_at
        else "-"
    )
    return {
        "request_id": request.request_id,
        "employee_id": employee.employee_id,
        "employee_name": employee.name,
        "department": employee.department,
        "leave_type": request.leave_type,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "days": request.days,
        "reason": request.reason,
        "status": request.status,
        "approver_id": request.approver_id,
        "submitted_at": submitted,
    }


def _format_leave_request(item: dict[str, Any]) -> str:
    return (
        f"{item['request_id']}：{item['employee_name']}，"
        f"{item['start_date']} 至 {item['end_date']}，"
        f"{item['days']:g} 天，状态：{item['status']}，"
        f"审批人：{item['approver_id']}，提交时间：{item['submitted_at']}"
    )


def get_my_leave_requests(
    employee_id: str,
    status: str | None = None,
) -> list[dict[str, Any]]:
    if status and status not in {"待审批", "已批准", "已拒绝", "已取消"}:
        raise ValueError(f"不支持的申请状态：{status}")
    db = SessionLocal()
    try:
        employee = _resolve_employee(db, employee_id=employee_id)
        query = db.query(LeaveRequest).filter(
            LeaveRequest.employee_id == employee.id
        )
        if status:
            query = query.filter(LeaveRequest.status == status)
        requests = query.order_by(LeaveRequest.submitted_at.desc()).all()
        return [
            _serialize_leave_request(request, employee) for request in requests
        ]
    finally:
        db.close()


def get_pending_approvals(manager_id: str) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        manager = _resolve_employee(db, employee_id=manager_id)
        if manager.role != "manager":
            raise ValueError("当前员工没有审批权限")
        rows = (
            db.query(LeaveRequest, Employee)
            .join(Employee, Employee.id == LeaveRequest.employee_id)
            .filter(
                LeaveRequest.approver_id == manager.employee_id,
                LeaveRequest.status == "待审批",
            )
            .order_by(LeaveRequest.submitted_at.asc())
            .all()
        )
        return [
            _serialize_leave_request(request, applicant)
            for request, applicant in rows
        ]
    finally:
        db.close()


def query_my_leave_requests(
    args: dict[str, Any], employee_id: str, role: str
) -> ToolResult:
    status = str(args.get("status", "")).strip()
    requests = get_my_leave_requests(employee_id, status or None)
    if not requests:
        return ToolResult("当前员工没有符合条件的请假申请。")
    return ToolResult(
        content="\n".join(_format_leave_request(item) for item in requests)
    )


def query_pending_approvals(
    args: dict[str, Any], employee_id: str, role: str
) -> ToolResult:
    requests = get_pending_approvals(employee_id)
    if not requests:
        return ToolResult("当前没有待审批的请假申请。")
    return ToolResult(
        content="\n".join(_format_leave_request(item) for item in requests)
    )


def query_pending_actions(
    args: dict[str, Any], employee_id: str, role: str
) -> ToolResult:
    db = SessionLocal()
    try:
        rows = (
            db.query(AgentAction)
            .filter(
                AgentAction.employee_id == employee_id,
                AgentAction.status == "待确认",
            )
            .order_by(AgentAction.created_at.desc())
            .all()
        )
        if not rows:
            return ToolResult("当前没有待确认的写操作。")
        lines = []
        for row in rows:
            try:
                payload = json.loads(row.payload_json or "{}")
            except json.JSONDecodeError:
                payload = {}
            lines.append(
                f"{row.action_id}：{row.summary}；参数："
                f"{json.dumps(payload, ensure_ascii=False)}"
            )
        return ToolResult(content="\n".join(lines))
    finally:
        db.close()


def revise_leave_request_draft(
    args: dict[str, Any], employee_id: str, role: str
) -> ToolResult:
    action_id = str(args.get("action_id", "")).strip()
    if not action_id:
        raise ValueError("缺少待修改的动作编号")
    update_fields = {
        key for key in ("start_date", "end_date", "days", "reason")
        if args.get(key) is not None and str(args.get(key)).strip() != ""
    }
    if not update_fields:
        raise ValueError("没有提供需要修改的内容")

    db = SessionLocal()
    try:
        row = (
            db.query(AgentAction)
            .filter(
                AgentAction.action_id == action_id,
                AgentAction.employee_id == employee_id,
            )
            .first()
        )
        if row is None:
            raise ValueError("未找到当前员工的待确认动作")
        if row.tool_name != "submit_leave_request":
            raise ValueError("只有请假申请草稿可以修改")
        if row.status != "待确认":
            raise ValueError(f"动作当前状态为“{row.status}”，不能修改")
        if row.expires_at and row.expires_at < datetime.now():
            row.status = "已过期"
            row.error_message = "待确认动作已过期"
            record_event(
                db,
                row.action_id,
                "expired",
                employee_id,
                {"reason": row.error_message},
            )
            db.commit()
            raise ValueError("待确认动作已过期，请重新发起申请")

        try:
            payload = json.loads(row.payload_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        employee = _resolve_employee(db, employee_id=employee_id)
        leave_type = str(payload.get("leave_type", "年假"))
        start_date = str(
            args.get("start_date") or payload.get("start_date", "")
        ).strip()
        end_date = str(
            args.get("end_date") or payload.get("end_date", "")
        ).strip()
        reason = str(
            args.get("reason") or payload.get("reason", "")
        ).strip()
        try:
            days = float(args.get("days") or payload.get("days"))
        except (TypeError, ValueError) as exc:
            raise ValueError("申请天数必须是数字") from exc

        approver_id = _validate_leave_values(
            db,
            employee,
            leave_type,
            start_date,
            end_date,
            days,
            reason,
        )
        revised = _build_pending_action(
            employee,
            approver_id,
            leave_type,
            start_date,
            end_date,
            days,
            reason,
            action_id=action_id,
        )
        return ToolResult(
            content=(
                f"已修改待确认请假草稿：{revised.summary}。"
                "请重新确认后再提交。"
            ),
            pending_action=revised,
        )
    finally:
        db.close()


def _build_review_action(
    action: str,
    request: LeaveRequest,
    applicant: Employee,
    approver_id: str,
    reason: str = "",
) -> PendingAction:
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    action_label = "批准" if action == "approve" else "拒绝"
    summary = (
        f"{action_label} {applicant.name} 的 {request.request_id}："
        f"{request.start_date} 至 {request.end_date}，{request.days:g} 天"
    )
    if reason:
        summary += f"，原因：{reason}"
    return PendingAction(
        action_id=f"ACT-{uuid.uuid4().hex[:8].upper()}",
        tool=f"{action}_leave_request",
        employee_id=approver_id,
        summary=summary,
        payload={
            "action": action,
            "request_id": request.request_id,
            "approver_id": approver_id,
            "reason": reason,
        },
        created_at=created_at,
    )


def _prepare_review_action(
    action: str,
    args: dict[str, Any],
    employee_id: str,
    role: str,
) -> ToolResult:
    request_id = str(args.get("request_id", "")).strip()
    reason = str(args.get("reason", "")).strip()
    if not request_id:
        raise ValueError("缺少申请编号")
    if action == "reject" and not reason:
        raise ValueError("拒绝申请必须填写原因")

    db = SessionLocal()
    try:
        approver = _resolve_employee(db, employee_id=employee_id)
        if approver.role != "manager":
            raise ValueError("当前员工没有审批权限")
        request = (
            db.query(LeaveRequest)
            .filter(LeaveRequest.request_id == request_id)
            .first()
        )
        if request is None:
            raise ValueError("请假申请不存在")
        if request.status != "待审批":
            raise ValueError(f"申请当前状态为“{request.status}”，不能审批")
        if request.approver_id != approver.employee_id:
            raise ValueError("只能审批分配给自己的申请")
        applicant = db.get(Employee, request.employee_id)
        if applicant is None:
            raise ValueError("申请人数据不存在")
        pending = _build_review_action(
            action,
            request,
            applicant,
            approver.employee_id,
            reason,
        )
        content = (
            f"已生成待确认的{ '批准' if action == 'approve' else '拒绝' }动作，"
            f"尚未修改申请状态。摘要：{pending.summary}。"
        )
    finally:
        db.close()
    return ToolResult(content=content, pending_action=pending)


def approve_leave_request(
    args: dict[str, Any], employee_id: str, role: str
) -> ToolResult:
    return _prepare_review_action("approve", args, employee_id, role)


def reject_leave_request(
    args: dict[str, Any], employee_id: str, role: str
) -> ToolResult:
    return _prepare_review_action("reject", args, employee_id, role)


def search_knowledge(args: dict[str, Any], employee_id: str, role: str) -> ToolResult:
    query = str(args.get("query", "")).strip()
    if not query:
        raise ValueError("检索词不能为空")
    chunks = retrieval.search(query, top_k=4, role=role)
    if not chunks:
        return ToolResult("知识库中没有找到相关内容。")

    lines: list[str] = []
    citations: list[dict] = []
    for index, chunk in enumerate(chunks, start=1):
        excerpt = chunk["content"]
        if len(excerpt) > 450:
            excerpt = excerpt[:450] + "……"
        lines.append(
            f"[{index}] 文档：{chunk['title']}；"
            f"章节：{chunk['heading']}；内容：{excerpt}"
        )
        citations.append(
            {
                "doc_id": chunk["doc_id"],
                "title": chunk["title"],
                "heading": chunk["heading"],
                "content": chunk["content"],
                "permission": chunk["permission"],
                "score": chunk["score"],
            }
        )
    return ToolResult(content="\n".join(lines), citations=citations)


def _build_pending_action(
    employee: Employee,
    approver_id: str,
    leave_type: str,
    start_date: str,
    end_date: str,
    days: float,
    reason: str,
    action_id: str | None = None,
) -> PendingAction:
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    return PendingAction(
        action_id=action_id or f"ACT-{uuid.uuid4().hex[:8].upper()}",
        tool="submit_leave_request",
        employee_id=employee.employee_id,
        summary=(
            f"{employee.name}申请{start_date}至{end_date}的{leave_type}"
            f"{days:g}天，审批人：{approver_id}，事由：{reason}"
        ),
        payload={
            "employee_id": employee.employee_id,
            "employee_name": employee.name,
            "approver_id": approver_id,
            "leave_type": leave_type,
            "start_date": start_date,
            "end_date": end_date,
            "days": days,
            "reason": reason,
        },
        created_at=created_at,
    )


def _validate_leave_values(
    db: Session,
    employee: Employee,
    leave_type: str,
    start_date: str,
    end_date: str,
    days: float,
    reason: str,
) -> str:
    if leave_type not in VALID_LEAVE_TYPES:
        raise ValueError("当前 Agent 版本仅支持年假申请")
    if not reason:
        raise ValueError("请填写请假事由")
    if days <= 0 or abs(days * 2 - round(days * 2)) > 1e-6:
        raise ValueError("年假天数应为 0.5 的正整数倍")

    start = _parse_date(start_date)
    end = _parse_date(end_date)
    weekday_count = _weekday_count(start, end)
    if weekday_count < days:
        raise ValueError(
            f"所选日期只包含 {weekday_count:g} 个工作日，"
            f"少于申请的 {days:g} 天"
        )

    balance = _get_balance(db, employee, DEMO_YEAR)
    remaining = balance.total_days - balance.used_days
    pending = _pending_days(db, employee, leave_type)
    available = remaining - pending
    duplicate = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.employee_id == employee.id,
            LeaveRequest.leave_type == leave_type,
            LeaveRequest.start_date == start_date,
            LeaveRequest.end_date == end_date,
            LeaveRequest.status == "待审批",
        )
        .first()
    )
    if duplicate:
        raise ValueError("该员工已有一条相同时间段的待审批年假申请")
    if days > available:
        raise ValueError(
            f"{employee.name} 当前可申请年假仅 {available:g} 天，"
            f"无法申请 {days:g} 天（账面余额 {remaining:g} 天，"
            f"待审批占用 {pending:g} 天）"
        )
    if employee.role == "employee":
        approver_id = (
            employee.manager_id
            if days <= 3
            else employee.department_head_id
        )
    else:
        approver_id = employee.manager_id or employee.department_head_id
    if not approver_id:
        raise ValueError("当前员工未配置对应审批人")
    if approver_id == employee.employee_id:
        raise ValueError("总经理账号没有更高级审批人，暂不支持发起请假")
    return approver_id


def submit_leave_request(
    args: dict[str, Any], employee_id: str, role: str
) -> ToolResult:
    employee_name = str(args.get("employee_name", "")).strip()
    leave_type = str(args.get("leave_type", "年假"))
    start_date = str(args.get("start_date", "")).strip()
    end_date = str(args.get("end_date", "")).strip()
    reason = str(args.get("reason", "")).strip()
    try:
        days = float(args.get("days"))
    except (TypeError, ValueError) as exc:
        raise ValueError("申请天数必须是数字") from exc

    db = SessionLocal()
    try:
        employee = _resolve_employee(
            db, employee_id=employee_id, employee_name=employee_name
        )
        if employee.employee_id != employee_id:
            raise ValueError("只能为当前会话员工提交申请")
        approver_id = _validate_leave_values(
            db,
            employee,
            leave_type,
            start_date,
            end_date,
            days,
            reason,
        )
        action = _build_pending_action(
            employee,
            approver_id,
            leave_type,
            start_date,
            end_date,
            days,
            reason,
        )
        content = (
            "已生成待确认的请假申请，未写入系统。"
            f"摘要：{action.summary}。确认前不会落库。"
        )
    finally:
        db.close()
    return ToolResult(content=content, pending_action=action)


def _commit_leave_request(action: PendingAction) -> tuple[str, float, float]:
    payload = action.payload
    db = SessionLocal()
    try:
        employee = _resolve_employee(db, employee_id=payload["employee_id"])
        balance = _get_balance(db, employee, DEMO_YEAR)
        remaining = balance.total_days - balance.used_days
        pending = _pending_days(db, employee, payload["leave_type"])
        available = remaining - pending
        days = float(payload["days"])
        if days > available:
            raise ValueError(
                f"{employee.name} 当前可申请年假仅 {available:g} 天，申请已失效"
            )
        approver_id = str(payload.get("approver_id") or "")
        if not approver_id:
            if employee.role == "employee":
                approver_id = (
                    employee.manager_id
                    if days <= 3
                    else employee.department_head_id
                )
            else:
                approver_id = (
                    employee.manager_id or employee.department_head_id
                )
        if not approver_id:
            raise ValueError("当前员工未配置对应审批人")
        if approver_id == employee.employee_id:
            raise ValueError("不能审批自己的申请")
        request_id = f"LV-{uuid.uuid4().hex[:10].upper()}"
        request = LeaveRequest(
            request_id=request_id,
            employee_id=employee.id,
            leave_type=payload["leave_type"],
            start_date=payload["start_date"],
            end_date=payload["end_date"],
            days=days,
            reason=payload["reason"],
            status="待审批",
            approver_id=approver_id,
            submitted_at=datetime.now(),
        )
        db.add(request)
        db.commit()
        return request_id, remaining, pending + days
    finally:
        db.close()


def _commit_review_action(action: PendingAction) -> dict[str, Any]:
    payload = action.payload
    decision = str(payload.get("action", ""))
    request_id = str(payload.get("request_id", ""))
    reason = str(payload.get("reason", "")).strip()

    db = SessionLocal()
    try:
        approver = _resolve_employee(db, employee_id=action.employee_id)
        if approver.role != "manager":
            raise ValueError("当前员工没有审批权限")
        request = (
            db.query(LeaveRequest)
            .filter(LeaveRequest.request_id == request_id)
            .first()
        )
        if request is None:
            raise ValueError("请假申请不存在")
        if request.status != "待审批":
            raise ValueError(f"申请当前状态为“{request.status}”，不能审批")
        if request.approver_id != approver.employee_id:
            raise ValueError("只能审批分配给自己的申请")

        if decision == "approve":
            applicant = _resolve_employee(
                db, employee_id=request.employee.employee_id
            )
            balance = _get_balance(db, applicant, DEMO_YEAR)
            if balance.used_days + request.days > balance.total_days:
                raise ValueError(
                    f"{applicant.name} 批准后将超过年假总额，不能批准"
                )
            balance.used_days = balance.used_days + request.days
            request.status = "已批准"
            request.approved_at = datetime.now()
            request.rejected_at = None
            request.reject_reason = ""
            remaining = balance.total_days - balance.used_days
        elif decision == "reject":
            if not reason:
                raise ValueError("拒绝申请必须填写原因")
            request.status = "已拒绝"
            request.rejected_at = datetime.now()
            request.reject_reason = reason
            applicant = request.employee
            balance = _get_balance(db, applicant, DEMO_YEAR)
            remaining = balance.total_days - balance.used_days
        else:
            raise ValueError(f"不支持的审批动作：{decision}")

        db.commit()
        return {
            "request_id": request.request_id,
            "status": request.status,
            "employee_id": applicant.employee_id,
            "employee_name": applicant.name,
            "remaining_days": remaining,
        }
    finally:
        db.close()


def execute_tool(
    name: str, args: dict[str, Any], employee_id: str, role: str
) -> ToolResult:
    if name == "query_leave_balance":
        return query_leave_balance(args, employee_id, role)
    if name == "query_my_leave_requests":
        return query_my_leave_requests(args, employee_id, role)
    if name == "query_pending_approvals":
        return query_pending_approvals(args, employee_id, role)
    if name == "query_pending_actions":
        return query_pending_actions(args, employee_id, role)
    if name == "revise_leave_request_draft":
        return revise_leave_request_draft(args, employee_id, role)
    if name == "approve_leave_request":
        return approve_leave_request(args, employee_id, role)
    if name == "reject_leave_request":
        return reject_leave_request(args, employee_id, role)
    if name == "search_knowledge":
        return search_knowledge(args, employee_id, role)
    if name == "submit_leave_request":
        return submit_leave_request(args, employee_id, role)
    raise ValueError(f"未知工具：{name}")
