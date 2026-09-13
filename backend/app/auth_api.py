from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import AuthUser, get_current_user, login, logout
from app.auth_schemas import (
    AuthUserOut,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_response(user: AuthUser) -> AuthUserOut:
    return AuthUserOut(
        employee_id=user.employee_id,
        username=user.username,
        name=user.name,
        department=user.department,
        position=user.position,
        role=user.role,
        manager_id=user.manager_id,
        department_head_id=user.department_head_id,
    )


@router.post("/login", response_model=LoginResponse)
def login_endpoint(payload: LoginRequest):
    try:
        token, expires_at, user = login(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return LoginResponse(
        token=token,
        expires_at=expires_at,
        user=_user_response(user),
    )


@router.get("/me", response_model=AuthUserOut)
def me(current_user: AuthUser = Depends(get_current_user)):
    return _user_response(current_user)


@router.post("/logout", response_model=LogoutResponse)
def logout_endpoint(
    request: Request,
    _current_user: AuthUser = Depends(get_current_user),
):
    authorization = request.headers.get("Authorization", "")
    token = authorization.removeprefix("Bearer ").strip()
    logout(token)
    return LogoutResponse(logged_out=True)
