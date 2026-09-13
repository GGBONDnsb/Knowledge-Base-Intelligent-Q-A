import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="kb_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_tmp, 'test.db')}"
os.environ["DEEPSEEK_API_KEY"] = "test-key"

import pytest
from fastapi.testclient import TestClient

from app import retrieval
from app.auth import DEMO_PASSWORD
from app.database import SessionLocal, init_db
from app.main import app
from app.models import Chunk, ChatLog, Document

DEMO_USERNAMES = {
    "E001": "zhangsan",
    "M001": "liming",
    "G001": "zhouzong",
    "A001": "admin",
}


@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    db = SessionLocal()
    try:
        db.query(ChatLog).delete()
        db.query(Chunk).delete()
        db.query(Document).delete()
        db.commit()
    finally:
        db.close()
    retrieval.index = retrieval.BM25Index()
    yield


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/auth/login",
            json={
                "username": DEMO_USERNAMES["E001"],
                "password": DEMO_PASSWORD,
            },
        )
        assert response.status_code == 200
        test_client.headers["Authorization"] = (
            f"Bearer {response.json()['token']}"
        )
        yield test_client


@pytest.fixture()
def as_user(client):
    def _switch(employee_id: str) -> TestClient:
        response = client.post(
            "/api/auth/login",
            json={
                "username": DEMO_USERNAMES.get(
                    employee_id, employee_id.lower()
                ),
                "password": DEMO_PASSWORD,
            },
        )
        assert response.status_code == 200
        client.headers["Authorization"] = (
            f"Bearer {response.json()['token']}"
        )
        return client

    return _switch
