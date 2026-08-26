from app import retrieval
from app.database import SessionLocal
from app.models import Chunk, Document


def _seed_doc(text: str) -> None:
    db = SessionLocal()
    try:
        doc = Document(
            doc_id="T-001",
            title="测试制度",
            filename="测试制度.md",
            category="制度类",
            permission="全员",
            owner="测试",
            status="已上传",
            source="测试",
            method="测试",
            update_date="2026-08-23",
        )
        doc.chunks.append(
            Chunk(
                chunk_index=0,
                heading="请假",
                content=text,
                char_count=len(text),
            )
        )
        db.add(doc)
        db.commit()
    finally:
        db.close()
    retrieval.build_index()


def test_empty_question_returns_400(client):
    resp = client.post("/api/chat", json={"question": "   "})
    assert resp.status_code == 400


def test_missing_key_returns_503(client, monkeypatch):
    monkeypatch.setattr("app.main.DEEPSEEK_API_KEY", "")
    resp = client.post("/api/chat", json={"question": "你好"})
    assert resp.status_code == 503


def test_chat_returns_answer_and_citations(client, monkeypatch):
    _seed_doc("事假应提前 1 天申请，审批通过后方可休假。")
    monkeypatch.setattr(
        "app.main.call_deepseek",
        lambda messages: "根据测试制度，事假应提前 1 天申请。",
    )
    resp = client.post("/api/chat", json={"question": "事假要提前几天申请？"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["refused"] is False
    assert "事假应提前 1 天申请" in data["answer"]
    assert data["citations"]
    assert data["citations"][0]["doc_id"] == "T-001"

def _seed_permission_docs() -> None:
    db = SessionLocal()
    try:
        doc_all = Document(
            doc_id="P-001",
            title="全员文档",
            filename="all.md",
            category="制度类",
            permission="全员",
            owner="测试",
            status="已上传",
            source="测试",
            method="测试",
            update_date="2026-08-26",
        )
        doc_all.chunks.append(
            Chunk(chunk_index=0, heading="考勤", content="普通员工应遵守考勤制度。", char_count=10)
        )
        doc_admin = Document(
            doc_id="P-002",
            title="管理员文档",
            filename="admin.md",
            category="制度类",
            permission="管理员",
            owner="测试",
            status="已上传",
            source="测试",
            method="测试",
            update_date="2026-08-26",
        )
        doc_admin.chunks.append(
            Chunk(chunk_index=0, heading="密码", content="管理员专属：账号密码长度不少于 12 位。", char_count=18)
        )
        db.add(doc_all)
        db.add(doc_admin)
        db.commit()
    finally:
        db.close()
    retrieval.build_index()


def test_employee_cannot_see_admin_doc(client, monkeypatch):
    _seed_permission_docs()
    monkeypatch.setattr("app.main.call_deepseek", lambda messages: "答案")
    resp = client.post("/api/chat", json={"question": "账号密码长度不少于多少位？", "role": "employee"})
    data = resp.json()
    assert not any(item["doc_id"] == "P-002" for item in data["citations"])


def test_admin_can_see_admin_doc(client, monkeypatch):
    _seed_permission_docs()
    monkeypatch.setattr("app.main.call_deepseek", lambda messages: "答案")
    resp = client.post("/api/chat", json={"question": "账号密码长度不少于多少位？", "role": "admin"})
    data = resp.json()
    assert any(item["doc_id"] == "P-002" for item in data["citations"])
