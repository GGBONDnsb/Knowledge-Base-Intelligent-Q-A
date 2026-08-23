from __future__ import annotations

import re
import uuid
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlalchemy import func

from app import retrieval
from app.database import SessionLocal
from app.ingest import chunk_document
from app.models import Chunk, Document
from app.schemas import DeleteResult, DocumentItem, ReindexResult, UploadResult

router = APIRouter(prefix="/api/documents", tags=["documents"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads"
ALLOWED_SUFFIXES = {".md", ".markdown", ".txt", ".html", ".htm"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return unescape("\n".join(parser.parts))


def _decode(data: bytes) -> str:
    for encoding in ("utf-8", "gbk", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _safe_filename(filename: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "-", filename)


@router.get("", response_model=list[DocumentItem])
def list_documents():
    db = SessionLocal()
    try:
        rows = (
            db.query(Document, func.count(Chunk.id))
            .outerjoin(Chunk, Chunk.document_id == Document.id)
            .group_by(Document.id)
            .order_by(Document.doc_id)
            .all()
        )
        return [
            DocumentItem(
                doc_id=doc.doc_id,
                title=doc.title,
                category=doc.category,
                permission=doc.permission,
                owner=doc.owner,
                status=doc.status,
                filename=doc.filename,
                chunk_count=count,
            )
            for doc, count in rows
        ]
    finally:
        db.close()


@router.post("/upload", response_model=UploadResult)
async def upload_document(file: UploadFile = File(...)):
    filename = file.filename or "未命名.txt"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"仅支持 {', '.join(sorted(ALLOWED_SUFFIXES))} 格式",
        )

    data = await file.read()
    text = _decode(data)
    if suffix in (".html", ".htm"):
        text = html_to_text(text)

    doc_id = f"UPL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"
    safe_name = _safe_filename(filename)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_path = UPLOAD_DIR / f"{doc_id}-{safe_name}"
    saved_path.write_bytes(data)

    db = SessionLocal()
    try:
        doc = Document(
            doc_id=doc_id,
            title=Path(filename).stem,
            filename=safe_name,
            category="其他",
            source="用户上传",
            method="网页上传",
            update_date=datetime.now().strftime("%Y-%m-%d"),
            permission="全员",
            owner="管理员",
            status="已上传",
            remark="网页上传文档",
            file_path=str(saved_path),
        )
        for index, item in enumerate(chunk_document(text.strip())):
            doc.chunks.append(
                Chunk(
                    chunk_index=index,
                    heading=item["heading"],
                    content=item["content"],
                    char_count=len(item["content"]),
                )
            )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        chunk_count = len(doc.chunks)
    finally:
        db.close()

    retrieval.build_index()
    return UploadResult(doc_id=doc_id, title=doc.title, chunk_count=chunk_count)


@router.delete("/{doc_id}", response_model=DeleteResult)
def delete_document(doc_id: str):
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.doc_id == doc_id).first()
        if doc is None:
            raise HTTPException(status_code=404, detail="文档不存在")
        db.delete(doc)
        db.commit()
    finally:
        db.close()
    retrieval.build_index()
    return DeleteResult(deleted=True)


@router.post("/reindex", response_model=ReindexResult)
def reindex_documents():
    db = SessionLocal()
    try:
        documents = db.query(Document).count()
        chunks = db.query(Chunk).count()
    finally:
        db.close()
    retrieval.build_index()
    return ReindexResult(documents=documents, chunks=chunks)
