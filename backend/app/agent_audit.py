from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import AuthUser
from app.database import SessionLocal
from app.models import (
    ActionEvent,
    AgentAction,
    Employee,
    LeaveRequest,
)

EVENT_TYPES = {
    "created",
    "confirmed",
    "executed",
    "failed",
    "cancelled",
    "expired",
}


def record_event(
    db: Session,
    action_id: str,
    event_type: str,
    actor_employee_id: str,
    detail: dict[str, Any] | None = None,
) -> ActionEvent:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"不支持的事件类型：{event_type}")
    event = ActionEvent(
        event_id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
        action_id=action_id,
        event_type=event_type,
        actor_employee_id=actor_employee_id,
        detail_json=json.dumps(detail or {}, ensure_ascii=False),
        created_at=datetime.now(),
    )
    db.add(event)
    return event


def _load_json(value: str) -> dict[str, Any]:
    try:
        data = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _format_time(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


def _visible_rows(
    db: Session, current_user: AuthUser
) -> list[AgentAction]:
    rows = db.query(AgentAction).order_by(AgentAction.created_at.desc()).all()
    if current_user.role == "admin":
        return rows
    if current_user.role == "manager":
        subordinate_ids = {
            employee_id
            for employee_id, in (
                db.query(Employee.employee_id)
                .filter(
                    (Employee.manager_id == current_user.employee_id)
                    | (
                        Employee.department_head_id
                        == current_user.employee_id
                    )
                )
                .all()
            )
        }
        subordinate_ids.add(current_user.employee_id)
        return [
            row for row in rows if row.employee_id in subordinate_ids
        ]
    return [
        row for row in rows if row.employee_id == current_user.employee_id
    ]


def list_actions(
    current_user: AuthUser,
    status: str | None = None,
    tool_name: str | None = None,
) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = _visible_rows(db, current_user)
        if status:
            rows = [row for row in rows if row.status == status]
        if tool_name:
            rows = [row for row in rows if row.tool_name == tool_name]
        if not rows:
            return []

        action_ids = [row.action_id for row in rows]
        actor_ids = {row.employee_id for row in rows}
        names = {
            employee.employee_id: employee.name
            for employee in db.query(Employee)
            .filter(Employee.employee_id.in_(actor_ids))
            .all()
        }
        event_counts = {
            action_id: count
            for action_id, count in (
                db.query(
                    ActionEvent.action_id,
                    func.count(ActionEvent.id),
                )
                .filter(ActionEvent.action_id.in_(action_ids))
                .group_by(ActionEvent.action_id)
                .all()
            )
        }
        return [
            _serialize_action(
                row,
                names.get(row.employee_id, row.employee_id),
                int(event_counts.get(row.action_id, 0)),
            )
            for row in rows
        ]
    finally:
        db.close()


def _serialize_action(
    row: AgentAction,
    actor_name: str,
    event_count: int,
) -> dict[str, Any]:
    return {
        "action_id": row.action_id,
        "session_id": row.session_id,
        "actor_employee_id": row.employee_id,
        "actor_name": actor_name,
        "tool_name": row.tool_name,
        "summary": row.summary,
        "status": row.status,
        "created_at": _format_time(row.created_at),
        "expires_at": _format_time(row.expires_at),
        "confirmed_at": _format_time(row.confirmed_at),
        "cancelled_at": _format_time(row.cancelled_at),
        "executed_at": _format_time(row.executed_at),
        "result": _load_json(row.result_json),
        "error_message": row.error_message,
        "event_count": event_count,
    }


def get_action_detail(
    current_user: AuthUser,
    action_id: str,
) -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        row = next(
            (
                item
                for item in _visible_rows(db, current_user)
                if item.action_id == action_id
            ),
            None,
        )
        if row is None:
            return None

        events = (
            db.query(ActionEvent)
            .filter(ActionEvent.action_id == action_id)
            .order_by(ActionEvent.created_at.asc())
            .all()
        )
        actor_ids = {event.actor_employee_id for event in events}
        actor_ids.add(row.employee_id)
        names = {
            employee.employee_id: employee.name
            for employee in db.query(Employee)
            .filter(Employee.employee_id.in_(actor_ids))
            .all()
        }
        detail = _serialize_action(
            row,
            names.get(row.employee_id, row.employee_id),
            len(events),
        )
        detail["payload"] = _load_json(row.payload_json)
        detail["events"] = [
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "actor_employee_id": event.actor_employee_id,
                "actor_name": names.get(
                    event.actor_employee_id,
                    event.actor_employee_id,
                ),
                "detail": _load_json(event.detail_json),
                "created_at": _format_time(event.created_at),
            }
            for event in events
        ]

        request_id = (
            detail["payload"].get("request_id")
            or detail["result"].get("request_id")
        )
        detail["related_request"] = None
        if request_id:
            request = (
                db.query(LeaveRequest)
                .filter(LeaveRequest.request_id == request_id)
                .first()
            )
            if request is not None:
                detail["related_request"] = {
                    "request_id": request.request_id,
                    "status": request.status,
                    "employee_id": request.employee.employee_id,
                    "employee_name": request.employee.name,
                    "start_date": request.start_date,
                    "end_date": request.end_date,
                    "days": request.days,
                }
        return detail
    finally:
        db.close()
