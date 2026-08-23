import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="kb_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_tmp, 'test.db')}"
os.environ["DEEPSEEK_API_KEY"] = "test-key"

import pytest
from fastapi.testclient import TestClient

from app import retrieval
from app.database import SessionLocal, init_db
from app.main import app
from app.models import Chunk, ChatLog, Document


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
        yield test_client
