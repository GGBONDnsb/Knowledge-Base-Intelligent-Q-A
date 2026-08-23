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
