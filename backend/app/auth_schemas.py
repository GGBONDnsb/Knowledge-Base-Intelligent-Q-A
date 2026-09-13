from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AuthUserOut(BaseModel):
    employee_id: str
    username: str
    name: str
    department: str
    position: str
    role: str
    manager_id: str
    department_head_id: str


class LoginResponse(BaseModel):
    token: str
    expires_at: datetime
    user: AuthUserOut


class LogoutResponse(BaseModel):
    logged_out: bool
