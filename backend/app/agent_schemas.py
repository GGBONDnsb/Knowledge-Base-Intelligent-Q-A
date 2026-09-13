from pydantic import BaseModel, Field

from app.schemas import Citation


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None


class PendingActionOut(BaseModel):
    action_id: str
    tool: str
    summary: str
    payload: dict
    created_at: str


class AgentChatResponse(BaseModel):
    session_id: str
    answer: str
    citations: list[Citation] = []
    pending_action: PendingActionOut | None = None
    steps: int = 0


class AgentActionConfirmResponse(BaseModel):
    action_id: str
    status: str
    request_id: str | None = None
    message: str


class AgentActionCancelResponse(BaseModel):
    action_id: str
    status: str
    message: str


class AgentEmployeeItem(BaseModel):
    employee_id: str
    name: str
    department: str
    position: str
    role: str
    manager_id: str
    department_head_id: str


class AgentLeaveRequestItem(BaseModel):
    request_id: str
    employee_id: str
    employee_name: str
    department: str
    leave_type: str
    start_date: str
    end_date: str
    days: float
    reason: str
    status: str
    approver_id: str
    submitted_at: str


class AgentActionEventOut(BaseModel):
    event_id: str
    event_type: str
    actor_employee_id: str
    actor_name: str
    detail: dict
    created_at: str | None = None


class AgentActionAuditItem(BaseModel):
    action_id: str
    session_id: str
    actor_employee_id: str
    actor_name: str
    tool_name: str
    summary: str
    status: str
    created_at: str | None = None
    expires_at: str | None = None
    confirmed_at: str | None = None
    cancelled_at: str | None = None
    executed_at: str | None = None
    result: dict
    error_message: str
    event_count: int


class AgentActionAuditDetail(AgentActionAuditItem):
    payload: dict
    events: list[AgentActionEventOut]
    related_request: dict | None = None


class DemoResetResponse(BaseModel):
    employees: int
    balances: int
    leave_requests: int


class RejectionPrepareRequest(BaseModel):
    reason: str = Field(min_length=1)
