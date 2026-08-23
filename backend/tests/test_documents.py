from app import retrieval
from app.database import SessionLocal
from app.models import Chunk, Document


def _seed_doc() -> None:
    db = SessionLocal()
    try:
        doc = Document(
            doc_id="T-002",
            title="测试文档",
            filename="测试文档.md",
            category="其他",
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
                heading="说明",
                content="这是用于测试的文档内容。",
                char_count=12,
            )
        )
        db.add(doc)
        db.commit()
    finally:
        db.close()
    retrieval.build_index()


def test_list_documents_after_seed(client):
    _seed_doc()
    resp = client.get("/api/documents")
    assert resp.status_code == 200
    items = resp.json()
    assert any(item["doc_id"] == "T-002" for item in items)


def test_upload_then_delete(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.documents_api.UPLOAD_DIR", tmp_path)
    resp = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "新制度.md",
                ("# 新制度\n\n## 加班\n\n工作日加班按 150% 支付。").encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["doc_id"].startswith("UPL-")
    assert data["chunk_count"] >= 1

    list_resp = client.get("/api/documents").json()
    assert any(item["doc_id"] == data["doc_id"] for item in list_resp)

    del_resp = client.delete(f"/api/documents/{data['doc_id']}")
    assert del_resp.status_code == 200

    list_resp2 = client.get("/api/documents").json()
    assert not any(item["doc_id"] == data["doc_id"] for item in list_resp2)


def test_reindex(client):
    _seed_doc()
    resp = client.post("/api/documents/reindex")
    assert resp.status_code == 200
    data = resp.json()
    assert data["documents"] == 1
    assert data["chunks"] == 1


def test_stats(client):
    _seed_doc()
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["documents"] == 1
    assert data["chunks"] == 1
    assert data["categories"].get("其他") == 1

