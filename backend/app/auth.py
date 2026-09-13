from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import AuthSession, Employee, UserAccount

SESSION_HOURS = 8
PBKDF2_ITERATIONS = 120_000
DEMO_PASSWORD = "Demo@123"

DEMO_ACCOUNTS = [
    {"employee_id": "E001", "username": "zhangsan"},
    {"employee_id": "M001", "username": "liming"},
    {"employee_id": "G001", "username": "zhouzong"},
    {"employee_id": "A001", "username": "admin"},
]


@dataclass(frozen=True)
class AuthUser:
    employee_id: str
    username: str
    name: str
    department: str
    position: str
    role: str
    manager_id: str
    department_head_id: str


def _hash_password(password: str, salt: str | None = None) -> str:
    actual_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        actual_salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${actual_salt}${digest}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        ).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, expected)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _to_auth_user(employee: Employee, username: str) -> AuthUser:
    return AuthUser(
        employee_id=employee.employee_id,
        username=username,
        name=employee.name,
        department=employee.department,
        position=employee.position,
        role=employee.role,
        manager_id=employee.manager_id,
        department_head_id=employee.department_head_id,
    )


def ensure_demo_accounts(db: Session) -> None:
    for item in DEMO_ACCOUNTS:
        employee = (
            db.query(Employee)
            .filter(Employee.employee_id == item["employee_id"])
            .first()
        )
        if employee is None:
            raise ValueError(f"演示账号缺少员工：{item['employee_id']}")
        account = (
            db.query(UserAccount)
            .filter(UserAccount.username == item["username"])
            .first()
        )
        if account is None:
            account = UserAccount(
                employee_id=employee.employee_id,
                username=item["username"],
                password_hash=_hash_password(DEMO_PASSWORD),
                status="active",
            )
            db.add(account)
        else:
            account.employee_id = employee.employee_id
            account.status = "active"

    db.flush()
    for employee in db.query(Employee).all():
        existing = (
            db.query(UserAccount)
            .filter(UserAccount.employee_id == employee.employee_id)
            .first()
        )
        if existing is not None:
            continue
        db.add(
            UserAccount(
                employee_id=employee.employee_id,
                username=employee.employee_id.lower(),
                password_hash=_hash_password(DEMO_PASSWORD),
                status="active",
            )
        )
    db.commit()


def login(username: str, password: str) -> tuple[str, datetime, AuthUser]:
    db = SessionLocal()
    try:
        account = (
            db.query(UserAccount)
            .filter(UserAccount.username == username.strip())
            .first()
        )
        if (
            account is None
            or account.status != "active"
            or not _verify_password(password, account.password_hash)
        ):
            raise ValueError("用户名或密码错误")
        employee = (
            db.query(Employee)
            .filter(Employee.employee_id == account.employee_id)
            .first()
        )
        if employee is None:
            raise ValueError("账号对应的员工不存在")

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=SESSION_HOURS)
        db.add(
            AuthSession(
                token_hash=_hash_token(token),
                employee_id=employee.employee_id,
                expires_at=expires_at,
            )
        )
        account.last_login_at = datetime.now()
        db.commit()
        return token, expires_at, _to_auth_user(employee, account.username)
    finally:
        db.close()


def get_user_by_token(token: str) -> AuthUser | None:
    db = SessionLocal()
    try:
        session = (
            db.query(AuthSession)
            .filter(AuthSession.token_hash == _hash_token(token))
            .first()
        )
        if (
            session is None
            or session.revoked_at is not None
            or session.expires_at <= datetime.now()
        ):
            return None
        employee = (
            db.query(Employee)
            .filter(Employee.employee_id == session.employee_id)
            .first()
        )
        if employee is None:
            return None
        account = (
            db.query(UserAccount)
            .filter(UserAccount.employee_id == employee.employee_id)
            .first()
        )
        session.last_seen_at = datetime.now()
        db.commit()
        return _to_auth_user(employee, account.username if account else "")
    finally:
        db.close()


def logout(token: str) -> None:
    db = SessionLocal()
    try:
        session = (
            db.query(AuthSession)
            .filter(AuthSession.token_hash == _hash_token(token))
            .first()
        )
        if session is not None and session.revoked_at is None:
            session.revoked_at = datetime.now()
            db.commit()
    finally:
        db.close()


def get_current_user(
    authorization: str | None = Header(default=None),
) -> AuthUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="请先登录")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="登录令牌无效")
    user = get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return user
