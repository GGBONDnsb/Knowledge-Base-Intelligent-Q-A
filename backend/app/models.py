from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    doc_id = Column(String, unique=True, index=True)
    title = Column(String, default="")
    filename = Column(String, default="")
    category = Column(String, default="")
    source = Column(String, default="")
    method = Column(String, default="")
    update_date = Column(String, default="")
    permission = Column(String, default="")
    owner = Column(String, default="")
    status = Column(String, default="")
    remark = Column(String, default="")
    source_url = Column(String, default="")
    license = Column(String, default="")
    file_path = Column(String, default="")
    imported_at = Column(DateTime, default=datetime.utcnow)

    chunks = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True)
    document_id = Column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index = Column(Integer, default=0)
    heading = Column(String, default="")
    content = Column(Text, default="")
    char_count = Column(Integer, default=0)

    document = relationship("Document", back_populates="chunks")


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True)
    question = Column(Text, default="")
    answer = Column(Text, default="")
    refused = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True)
    employee_id = Column(String, unique=True, index=True)
    name = Column(String, default="")
    department = Column(String, default="")
    position = Column(String, default="")
    work_years = Column(Integer, default=0)
    role = Column(String, default="employee")
    manager_id = Column(String, default="", index=True)
    department_head_id = Column(String, default="", index=True)

    leave_balances = relationship(
        "LeaveBalance", back_populates="employee", cascade="all, delete-orphan"
    )
    leave_requests = relationship(
        "LeaveRequest", back_populates="employee", cascade="all, delete-orphan"
    )


class LeaveBalance(Base):
    __tablename__ = "leave_balances"
    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "year",
            "leave_type",
            name="uq_leave_balance_employee_year_type",
        ),
    )

    id = Column(Integer, primary_key=True)
    employee_id = Column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), index=True
    )
    year = Column(Integer, default=2026, index=True)
    leave_type = Column(String, default="年假")
    total_days = Column(Float, default=0)
    used_days = Column(Float, default=0)

    employee = relationship("Employee", back_populates="leave_balances")


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True)
    request_id = Column(String, unique=True, index=True)
    employee_id = Column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), index=True
    )
    leave_type = Column(String, default="年假")
    start_date = Column(String, default="")
    end_date = Column(String, default="")
    days = Column(Float, default=0)
    reason = Column(String, default="")
    status = Column(String, default="待审批")
    approver_id = Column(String, default="", index=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    reject_reason = Column(Text, default="")
    cancelled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee", back_populates="leave_requests")


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id = Column(Integer, primary_key=True)
    session_id = Column(String, unique=True, index=True)
    employee_id = Column(String, default="")
    role = Column(String, default="employee")
    messages = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AgentAction(Base):
    __tablename__ = "agent_actions"

    id = Column(Integer, primary_key=True)
    action_id = Column(String, unique=True, index=True)
    session_id = Column(String, default="", index=True)
    employee_id = Column(String, default="", index=True)
    tool_name = Column(String, default="")
    summary = Column(Text, default="")
    payload_json = Column(Text, default="{}")
    status = Column(String, default="待确认", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True)
    result_json = Column(Text, default="")
    error_message = Column(Text, default="")


class ActionEvent(Base):
    __tablename__ = "action_events"

    id = Column(Integer, primary_key=True)
    event_id = Column(String, unique=True, index=True)
    action_id = Column(String, index=True)
    event_type = Column(String, index=True)
    actor_employee_id = Column(String, default="", index=True)
    detail_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String, primary_key=True)
    value = Column(Text, default="")
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class UserAccount(Base):
    __tablename__ = "user_accounts"

    id = Column(Integer, primary_key=True)
    employee_id = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String, default="")
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id = Column(Integer, primary_key=True)
    token_hash = Column(String, unique=True, index=True)
    employee_id = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    revoked_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
