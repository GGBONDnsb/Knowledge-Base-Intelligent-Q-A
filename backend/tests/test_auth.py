from fastapi.testclient import TestClient

from app.auth import DEMO_PASSWORD
from app.main import app


def test_login_and_current_user(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["employee_id"] == "E001"


def test_login_rejects_wrong_password(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "zhangsan", "password": "wrong"},
    )
    assert response.status_code == 401


def test_unauthenticated_agent_request_returns_401():
    with TestClient(app) as test_client:
        response = test_client.get("/api/agent/leave-requests")
    assert response.status_code == 401


def test_logout_revokes_current_token(client):
    assert client.get("/api/auth/me").status_code == 200
    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200
    assert logout.json()["logged_out"] is True
    assert client.get("/api/auth/me").status_code == 401


def test_identity_query_parameter_cannot_switch_employee(client, as_user):
    as_user("M001")
    response = client.get(
        "/api/agent/leave-requests",
        params={"employee_id": "E001"},
    )
    assert response.status_code == 200
    assert all(item["employee_id"] == "M001" for item in response.json())


def test_demo_account_seed_supports_manager_login(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "liming", "password": DEMO_PASSWORD},
    )
    assert response.status_code == 200
    assert response.json()["user"]["employee_id"] == "M001"
