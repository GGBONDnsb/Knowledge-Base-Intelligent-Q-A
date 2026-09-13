from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from openai import OpenAI

from app.agent_audit import record_event
from app.agent_data import DEMO_YEAR, ensure_demo_data
from app.agent_tools import (
    PendingAction,
    TOOL_SPECS,
    _commit_leave_request,
    _commit_review_action,
    execute_tool,
)
from app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL_NAME
from app.database import SessionLocal
from app.models import ActionEvent, AgentAction, AgentSession, Employee

MAX_AGENT_TURNS = 6

SYSTEM_PROMPT = """你是云启科技的业务助手。
你可以通过工具读取真实数据，也可以调用知识库检索回答制度、产品和技术问题。
必须遵守：
1. 年假余额、已用天数只以 query_leave_balance 的真实返回为准，不得估算或编造。
2. 知识库内容只以 search_knowledge 的真实返回为准。
3. 年假申请走 submit_leave_request；它只会生成待确认动作，不会立即写入数据库。
4. 查询自己的申请使用 query_my_leave_requests，主管查询待办使用 query_pending_approvals。
5. 批准或拒绝申请前必须调用对应工具生成待确认动作，不能直接宣称审批成功。
6. 普通员工只能查询自己的申请，只有申请上指定的审批人可以审批。
7. 主管或管理员可以发起自己的请假，审批人由系统指定为总经理，不能自审。
8. 用户明确要求批准或拒绝时，即使已经查询过申请，也必须继续调用
   approve_leave_request 或 reject_leave_request，禁止只口头声称已生成动作。
9. 需要用户确认时，用自然语言说明申请摘要，并告诉用户稍后点击确认。
10. 回答使用中文，简洁、准确。"""


@dataclass
class AgentResult:
    session_id: str
    answer: str
    citations: list[dict] = field(default_factory=list)
    pending_action: PendingAction | None = None
    steps: int = 0
    tools_used: list[str] = field(default_factory=list)


class PendingActionStore:
    ACTION_TTL = timedelta(minutes=10)

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def clear(self) -> None:
        with self._lock:
            db = SessionLocal()
            try:
                db.query(ActionEvent).delete()
                db.query(AgentAction).delete()
                db.commit()
            finally:
                db.close()

    @staticmethod
    def _row_to_action(row: AgentAction) -> PendingAction:
        try:
            payload = json.loads(row.payload_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        return PendingAction(
            action_id=row.action_id,
            tool=row.tool_name,
            employee_id=row.employee_id,
            summary=row.summary,
            payload=payload,
            created_at=(
                row.created_at.isoformat(timespec="seconds")
                if row.created_at
                else ""
            ),
        )

    def put(self, action: PendingAction, session_id: str = "") -> None:
        with self._lock:
            db = SessionLocal()
            try:
                row = (
                    db.query(AgentAction)
                    .filter(AgentAction.action_id == action.action_id)
                    .first()
                )
                if row is None:
                    row = AgentAction(action_id=action.action_id)
                    db.add(row)
                    is_new = True
                else:
                    is_new = False
                created_at = (
                    datetime.fromisoformat(action.created_at)
                    if action.created_at
                    else datetime.now()
                )
                row.session_id = session_id
                row.employee_id = action.employee_id
                row.tool_name = action.tool
                row.summary = action.summary
                row.payload_json = json.dumps(action.payload, ensure_ascii=False)
                row.status = "待确认"
                row.created_at = created_at
                row.expires_at = created_at + self.ACTION_TTL
                row.confirmed_at = None
                row.cancelled_at = None
                row.executed_at = None
                row.result_json = ""
                row.error_message = ""
                if is_new:
                    record_event(
                        db,
                        action.action_id,
                        "created",
                        action.employee_id,
                        {
                            "tool_name": action.tool,
                            "summary": action.summary,
                            "payload": action.payload,
                        },
                    )
                db.commit()
            finally:
                db.close()

    def get(self, action_id: str) -> PendingAction | None:
        with self._lock:
            db = SessionLocal()
            try:
                row = (
                    db.query(AgentAction)
                    .filter(AgentAction.action_id == action_id)
                    .first()
                )
                if row is None or row.status != "待确认":
                    return None
                return self._row_to_action(row)
            finally:
                db.close()

    def confirm(
        self, action_id: str, employee_id: str | None = None
    ) -> tuple[str, str]:
        with self._lock:
            db = SessionLocal()
            try:
                row = (
                    db.query(AgentAction)
                    .filter(AgentAction.action_id == action_id)
                    .first()
                )
                if row is None:
                    raise KeyError(action_id)
                if employee_id and row.employee_id != employee_id:
                    raise ValueError("只能确认自己的操作")
                if row.status != "待确认":
                    raise ValueError(f"该动作当前状态为“{row.status}”，不能确认")
                if row.expires_at and row.expires_at < datetime.now():
                    row.status = "已过期"
                    row.error_message = "待确认动作已过期"
                    record_event(
                        db,
                        row.action_id,
                        "expired",
                        employee_id or row.employee_id,
                        {"reason": row.error_message},
                    )
                    db.commit()
                    raise ValueError("待确认动作已过期，请重新发起申请")
                row.confirmed_at = datetime.now()
                record_event(
                    db,
                    row.action_id,
                    "confirmed",
                    employee_id or row.employee_id,
                    {"tool_name": row.tool_name},
                )
                db.commit()
                action = self._row_to_action(row)
            finally:
                db.close()

            try:
                if action.tool == "submit_leave_request":
                    request_id, remaining, pending_days = (
                        _commit_leave_request(action)
                    )
                    result = {
                        "request_id": request_id,
                        "remaining_days": remaining,
                        "pending_days": pending_days,
                    }
                    message = (
                        f"请假申请已确认并提交，单号 {request_id}，"
                        f"账面余额 {remaining:g} 天，"
                        f"待审批共占用 {pending_days:g} 天。"
                    )
                elif action.tool in {
                    "approve_leave_request",
                    "reject_leave_request",
                }:
                    result = _commit_review_action(action)
                    request_id = str(result["request_id"])
                    message = (
                        f"申请 {request_id} 已{result['status']}，"
                        f"{result['employee_name']} 当前账面年假余额为 "
                        f"{result['remaining_days']:g} 天。"
                    )
                else:
                    raise ValueError("该待确认动作不支持确认")
            except Exception as exc:
                db = SessionLocal()
                try:
                    row = (
                        db.query(AgentAction)
                        .filter(AgentAction.action_id == action_id)
                        .first()
                    )
                    if row is not None:
                        row.status = "执行失败"
                        row.error_message = str(exc)
                        record_event(
                            db,
                            row.action_id,
                            "failed",
                            employee_id or row.employee_id,
                            {"error": str(exc)},
                        )
                        db.commit()
                finally:
                    db.close()
                raise

            db = SessionLocal()
            try:
                row = (
                    db.query(AgentAction)
                    .filter(AgentAction.action_id == action_id)
                    .first()
                )
                if row is not None:
                    row.status = "已完成"
                    row.executed_at = datetime.now()
                    row.result_json = json.dumps(
                        result,
                        ensure_ascii=False,
                    )
                    record_event(
                        db,
                        row.action_id,
                        "executed",
                        employee_id or row.employee_id,
                        result,
                    )
                    db.commit()
            finally:
                db.close()
        return request_id, message

    def cancel(
        self, action_id: str, employee_id: str | None = None
    ) -> str:
        with self._lock:
            db = SessionLocal()
            try:
                row = (
                    db.query(AgentAction)
                    .filter(AgentAction.action_id == action_id)
                    .first()
                )
                if row is None:
                    raise KeyError(action_id)
                if employee_id and row.employee_id != employee_id:
                    raise ValueError("只能取消自己的操作")
                if row.status != "待确认":
                    raise ValueError(f"该动作当前状态为“{row.status}”，不能取消")
                row.status = "已取消"
                row.cancelled_at = datetime.now()
                record_event(
                    db,
                    row.action_id,
                    "cancelled",
                    employee_id or row.employee_id,
                    {"tool_name": row.tool_name},
                )
                db.commit()
            finally:
                db.close()
        return "待确认的请假申请已取消，未写入任何业务数据。"


pending_store = PendingActionStore()


def call_agent_model(
    messages: list[dict[str, Any]], tools: list[dict] | None = None
) -> Any:
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY，请在 backend/.env 中填写")
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    kwargs: dict[str, Any] = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.2,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message


def _model_message_to_dict(message: Any) -> dict:
    content = getattr(message, "content", None)
    tool_calls = getattr(message, "tool_calls", None) or []
    normalized_calls = []
    for call in tool_calls:
        normalized_calls.append(
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
        )
    item: dict[str, Any] = {"role": "assistant", "content": content}
    if normalized_calls:
        item["tool_calls"] = normalized_calls
    return item


def _load_conversation(session: AgentSession) -> list[dict[str, Any]]:
    try:
        data = json.loads(session.messages or "[]")
    except (TypeError, json.JSONDecodeError):
        data = []
    return [item for item in data if isinstance(item, dict)]


def _get_or_create_session(
    employee: Employee,
    role: str,
    session_id: str | None,
) -> tuple[AgentSession, str, list[dict[str, Any]]]:
    db = SessionLocal()
    try:
        session = None
        if session_id:
            session = (
                db.query(AgentSession)
                .filter(AgentSession.session_id == session_id)
                .first()
            )
            if session and session.employee_id != employee.employee_id:
                raise ValueError("session 与当前员工不匹配，请新建会话")
        if session is None:
            session = AgentSession(
                session_id=f"AGENT-{uuid.uuid4().hex[:12].upper()}",
                employee_id=employee.employee_id,
                role=role,
                messages="[]",
            )
            db.add(session)
            db.commit()
            db.refresh(session)
        return session, session.session_id, _load_conversation(session)
    finally:
        db.close()


def _save_conversation(
    session_id: str,
    conversation: list[dict[str, Any]],
) -> None:
    db = SessionLocal()
    try:
        session = (
            db.query(AgentSession)
            .filter(AgentSession.session_id == session_id)
            .first()
        )
        if session is None:
            return
        session.messages = json.dumps(conversation, ensure_ascii=False)
        db.commit()
    finally:
        db.close()


def _build_system_message(employee: Employee) -> dict[str, str]:
    today = datetime.now().date().isoformat()
    return {
        "role": "system",
        "content": (
            f"{SYSTEM_PROMPT}\n"
            f"今天是 {today}。当前会话员工：{employee.name}"
            f"（{employee.employee_id}，{employee.department}）。"
            f"年度余额基准年为 {DEMO_YEAR}。"
        ),
    }


def run_agent(
    message: str,
    employee_id: str,
    role: str,
    session_id: str | None = None,
) -> AgentResult:
    text = message.strip()
    if not text:
        raise ValueError("消息不能为空")

    db = SessionLocal()
    try:
        ensure_demo_data(db)
        employee = (
            db.query(Employee)
            .filter(Employee.employee_id == employee_id)
            .first()
        )
        if employee is None:
            raise ValueError(f"员工不存在：{employee_id}")
        session, resolved_session_id, conversation = _get_or_create_session(
            employee, role, session_id
        )
    finally:
        db.close()

    user_message = {"role": "user", "content": text}
    working_messages = [_build_system_message(employee), *conversation, user_message]
    citations: list[dict] = []
    pending_action: PendingAction | None = None
    answer = ""
    used_turns = 0
    tools_used: list[str] = []

    for _ in range(MAX_AGENT_TURNS):
        used_turns += 1
        model_message = call_agent_model(working_messages, TOOL_SPECS)
        working_messages.append(_model_message_to_dict(model_message))

        tool_calls = getattr(model_message, "tool_calls", None) or []
        if not tool_calls:
            answer = (model_message.content or "").strip()
            if not answer:
                answer = "我没有足够信息回答这个问题。"
            break

        for call in tool_calls:
            tools_used.append(call.function.name)
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            try:
                result = execute_tool(
                    call.function.name, args, employee.employee_id, role
                )
            except Exception as exc:
                result_content = f"工具执行失败：{exc}"
                pending = None
                result_citations: list[dict] = []
            else:
                result_content = result.content
                pending = result.pending_action
                result_citations = result.citations

            working_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result_content,
                }
            )
            citations.extend(result_citations)
            if pending is not None:
                pending_action = pending
                pending_store.put(pending, resolved_session_id)

        if pending_action is not None:
            final_message = call_agent_model(working_messages, TOOL_SPECS)
            working_messages.append(_model_message_to_dict(final_message))
            answer = (final_message.content or "").strip()
            if not answer:
                answer = (
                    "已生成待确认的请假申请："
                    f"{pending_action.summary}。请确认后提交。"
                )
            break
    else:
        answer = "本次任务已完成多轮工具调用但仍未结束，请重新描述需求或简化任务。"

    conversation.extend([user_message, {"role": "assistant", "content": answer}])
    _save_conversation(resolved_session_id, conversation)
    return AgentResult(
        session_id=resolved_session_id,
        answer=answer,
        citations=citations,
        pending_action=pending_action,
        steps=used_turns,
        tools_used=tools_used,
    )
