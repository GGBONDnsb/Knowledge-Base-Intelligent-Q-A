from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_

from app.agent_schemas import (
    AgentActionAuditDetail,
    AgentActionAuditItem,
    AgentActionCancelResponse,
    AgentActionConfirmResponse,
    AgentChatRequest,
    AgentChatResponse,
    AgentEmployeeItem,
    AgentLeaveRequestItem,
    DemoResetResponse,
    PendingActionOut,
    RejectionPrepareRequest,
)
from app.agent_audit import get_action_detail, list_actions
from app.agent_service import pending_store, run_agent
from app.agent_tools import (
    approve_leave_request,
    get_my_leave_requests,
    get_pending_approvals,
    reject_leave_request,
)
from app.auth import AuthUser, get_current_user
from app.database import SessionLocal
from app.interview_data_import import reset_interview_data
from app.models import Employee
from app.schemas import Citation

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _pending_response(action) -> PendingActionOut:
    return PendingActionOut(
        action_id=action.action_id,
        tool=action.tool,
        summary=action.summary,
        payload=action.payload,
        created_at=action.created_at,
    )


@router.get("/employees", response_model=list[AgentEmployeeItem])
def list_agent_employees(
    current_user: AuthUser = Depends(get_current_user),
):
    db = SessionLocal()
    try:
        query = db.query(Employee)
        if current_user.role == "admin":
            pass
        elif current_user.role == "manager":
            query = query.filter(
                or_(
                    Employee.employee_id == current_user.employee_id,
                    Employee.manager_id == current_user.employee_id,
                    Employee.department_head_id == current_user.employee_id,
                )
            )
        else:
            query = query.filter(
                Employee.employee_id == current_user.employee_id
            )
        employees = query.order_by(Employee.employee_id).all()
        return [
            AgentEmployeeItem(
                employee_id=item.employee_id,
                name=item.name,
                department=item.department,
                position=item.position,
                role=item.role,
                manager_id=item.manager_id,
                department_head_id=item.department_head_id,
            )
            for item in employees
        ]
    finally:
        db.close()


@router.get("/leave-requests", response_model=list[AgentLeaveRequestItem])
def list_my_leave_requests(
    status: str | None = None,
    current_user: AuthUser = Depends(get_current_user),
):
    try:
        return [
            AgentLeaveRequestItem(**item)
            for item in get_my_leave_requests(
                current_user.employee_id, status
            )
        ]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/approvals", response_model=list[AgentLeaveRequestItem])
def list_pending_approvals(
    current_user: AuthUser = Depends(get_current_user),
):
    try:
        return [
            AgentLeaveRequestItem(**item)
            for item in get_pending_approvals(current_user.employee_id)
        ]
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post(
    "/leave-requests/{request_id}/approve",
    response_model=PendingActionOut,
)
def prepare_approval(
    request_id: str,
    current_user: AuthUser = Depends(get_current_user),
):
    try:
        result = approve_leave_request(
            {"request_id": request_id},
            employee_id=current_user.employee_id,
            role=current_user.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if result.pending_action is None:
        raise HTTPException(status_code=500, detail="未生成待确认动作")
    pending_store.put(result.pending_action, session_id="TASK-CENTER")
    return _pending_response(result.pending_action)


@router.post(
    "/leave-requests/{request_id}/reject",
    response_model=PendingActionOut,
)
def prepare_rejection(
    request_id: str,
    payload: RejectionPrepareRequest,
    current_user: AuthUser = Depends(get_current_user),
):
    try:
        result = reject_leave_request(
            {"request_id": request_id, "reason": payload.reason},
            employee_id=current_user.employee_id,
            role=current_user.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if result.pending_action is None:
        raise HTTPException(status_code=500, detail="未生成待确认动作")
    pending_store.put(result.pending_action, session_id="TASK-CENTER")
    return _pending_response(result.pending_action)


@router.post("/chat", response_model=AgentChatResponse)
def agent_chat(
    payload: AgentChatRequest,
    current_user: AuthUser = Depends(get_current_user),
):
    try:
        result = run_agent(
            message=payload.message,
            employee_id=current_user.employee_id,
            role=current_user.role,
            session_id=payload.session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    pending = None
    if result.pending_action is not None:
        action = result.pending_action
        pending = PendingActionOut(
            action_id=action.action_id,
            tool=action.tool,
            summary=action.summary,
            payload=action.payload,
            created_at=action.created_at,
        )
    return AgentChatResponse(
        session_id=result.session_id,
        answer=result.answer,
        citations=[Citation(**item) for item in result.citations],
        pending_action=pending,
        steps=result.steps,
    )


@router.get("/actions", response_model=list[AgentActionAuditItem])
def list_action_audit(
    status: str | None = None,
    tool_name: str | None = None,
    current_user: AuthUser = Depends(get_current_user),
):
    return [
        AgentActionAuditItem(**item)
        for item in list_actions(current_user, status, tool_name)
    ]


@router.get(
    "/actions/{action_id}",
    response_model=AgentActionAuditDetail,
)
def get_action_audit_detail(
    action_id: str,
    current_user: AuthUser = Depends(get_current_user),
):
    detail = get_action_detail(current_user, action_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="操作记录不存在")
    return AgentActionAuditDetail(**detail)


@router.post("/demo/reset", response_model=DemoResetResponse)
def reset_demo(
    current_user: AuthUser = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="只有管理员可以重置演示数据")
    db = SessionLocal()
    try:
        result = reset_interview_data(db)
    finally:
        db.close()
    return DemoResetResponse(**result)


@router.post(
    "/actions/{action_id}/confirm",
    response_model=AgentActionConfirmResponse,
)
def confirm_action(
    action_id: str,
    current_user: AuthUser = Depends(get_current_user),
):
    try:
        request_id, message = pending_store.confirm(
            action_id, current_user.employee_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="待确认动作不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AgentActionConfirmResponse(
        action_id=action_id,
        status="confirmed",
        request_id=request_id,
        message=message,
    )


@router.delete(
    "/actions/{action_id}",
    response_model=AgentActionCancelResponse,
)
def cancel_action(
    action_id: str,
    current_user: AuthUser = Depends(get_current_user),
):
    try:
        message = pending_store.cancel(
            action_id, current_user.employee_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="待确认动作不存在") from exc
    return AgentActionCancelResponse(
        action_id=action_id,
        status="cancelled",
        message=message,
    )
