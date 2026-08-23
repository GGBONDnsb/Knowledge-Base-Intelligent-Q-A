from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import retrieval
from app.ingest import (
    chunk_document,
    extract_title,
    strip_metadata_and_frontmatter,
)
from app.models import Chunk, ChatLog, Document

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
ALLOWED_SUFFIXES = {".md", ".markdown", ".txt", ".html", ".htm"}

TAG_PATTERN = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return TAG_PATTERN.sub(" ", text)


def _safe_filename(name: str) -> str:
    safe = re.sub(r'[\\/:*?"<>|]+', "-", name)
    return safe or "document"


def list_documents(db: Session) -> list[dict]:
    rows = (
        db.query(Document, func.count(Chunk.id))
        .outerjoin(Chunk, Chunk.document_id == Document.id)
        .group_by(Document.id)
        .order_by(Document.doc_id)
        .all()
    )
    return [
        {
            "id": doc.id,
            "doc_id": doc.doc_id,
            "title": doc.title,
            "category": doc.category,
            "permission": doc.permission,
            "owner": doc.owner,
            "status": doc.status,
            "chunk_count": count,
        }
        for doc, count in rows
    ]


def delete_document(db: Session, doc_id: str) -> bool:
    doc = db.query(Document).filter(Document.doc_id == doc_id).first()
    if not doc:
        return False
    file_path = doc.file_path
    db.delete(doc)
    db.commit()
    if file_path:
        path = Path(file_path)
        if path.exists() and path.parent == UPLOAD_DIR.resolve():
            try:
                path.unlink()
            except OSError:
                pass
    retrieval.index.load()
    return True


def create_document_from_upload(filename: str, content: bytes) -> Document:
    text = content.decode("utf-8", errors="replace")
    suffix = Path(filename).suffix.lower()
    if suffix in (".html", ".htm"):
        text = _strip_html(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = strip_metadata_and_frontmatter(text)
    doc_id = (
        f"YQ-UPL-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-"
        f"{uuid.uuid4().hex[:6].upper()}"
    )
    title = extract_title(cleaned, text) or Path(filename).stem

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target = UPLOAD_DIR / f"{doc_id}-{_safe_filename(filename)}"
    target.write_text(text, encoding="utf-8")

    doc = Document(
        doc_id=doc_id,
        title=title,
        filename=filename,
        category="用户上传",
        source="用户上传",
        method="网页上传",
        update_date=datetime.utcnow().strftime("%Y-%m-%d"),
        permission="全员",
        owner="管理员",
        status="已上传",
        remark="通过管理页面上传",
        file_path=str(target),
    )
    for index, item in enumerate(chunk_document(cleaned)):
        doc.chunks.append(
            Chunk(
                chunk_index=index,
                heading=item["heading"],
                content=item["content"],
                char_count=len(item["content"]),
            )
        )
    return doc


def stats(db: Session) -> dict:
    categories = {
        category: count
        for category, count in (
            db.query(Document.category, func.count())
            .group_by(Document.category)
            .all()
        )
    }
    return {
        "documents": db.query(Document).count(),
        "chunks": db.query(Chunk).count(),
        "categories": categories,
        "question_count": db.query(ChatLog).count(),
    }
