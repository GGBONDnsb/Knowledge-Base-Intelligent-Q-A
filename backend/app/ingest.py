from __future__ import annotations

import csv
import os
import re
from pathlib import Path

from app.database import SessionLocal, init_db
from app.models import Chunk, Document

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_ROOT = Path(os.environ.get("DATA_ROOT", PROJECT_ROOT))
CLEAN_DIR = DATA_ROOT / "data" / "clean"
MANIFEST_PATH = DATA_ROOT / "data" / "meta" / "manifest.csv"

MAX_CHUNK_CHARS = 800

COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
FRONTMATTER_PATTERN = re.compile(r"\A---\s*\n.*?\n---\s*\n?", re.DOTALL)
HEADING_PATTERN = re.compile(r"^#{2,6}\s+(.+)$")
TITLE_PATTERN = re.compile(r"^#\s+\S")
FRONTMATTER_TITLE = re.compile(r"^title:\s*(.+)$", re.MULTILINE)
SENTENCE_SPLIT = re.compile(r"(?<=[。！？；!?])\s*|\n+")

META_KEY_MAP = {
    "文档编号": "doc_id",
    "类别": "category",
    "来源": "source",
    "获取方式": "method",
    "更新日期": "update_date",
    "权限级别": "permission",
    "负责人": "owner",
    "状态": "status",
    "备注": "remark",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_metadata_comment(text: str) -> dict:
    result = {}
    match = re.search(r"<!--(.*?)-->", text, re.DOTALL)
    if not match:
        return result
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            field = META_KEY_MAP.get(key.strip())
            if field and value.strip():
                result[field] = value.strip()
    return result


def strip_metadata_and_frontmatter(text: str) -> str:
    text = re.sub(COMMENT_PATTERN, "", text)
    text = re.sub(FRONTMATTER_PATTERN, "", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


def extract_title(text: str, raw: str = "") -> str:
    for line in text.splitlines():
        if TITLE_PATTERN.match(line):
            return line.lstrip("# ").strip()
    match = FRONTMATTER_TITLE.search(raw)
    if match:
        return match.group(1).strip().strip('"\'')
    return ""


def split_paragraph(text: str) -> list[str]:
    return [part.strip() for part in text.split("\n\n") if part.strip()]


def split_hard(text: str, limit: int) -> list[str]:
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def split_oversized_paragraph(paragraph: str, limit: int) -> list[str]:
    if len(paragraph) <= limit:
        return [paragraph]
    parts = [part.strip() for part in SENTENCE_SPLIT.split(paragraph) if part.strip()]
    result: list[str] = []
    current = ""
    for part in parts:
        if len(current) + len(part) + 1 <= limit:
            current = f"{current} {part}".strip()
        else:
            if current:
                result.append(current)
            if len(part) > limit:
                result.extend(split_hard(part, limit))
                current = ""
            else:
                current = part
    if current:
        result.append(current)
    return result or split_hard(paragraph, limit)


def split_content(content: str, limit: int) -> list[str]:
    if len(content) <= limit:
        return [content]
    parts: list[str] = []
    for paragraph in split_paragraph(content):
        if len(paragraph) <= limit:
            parts.append(paragraph)
        else:
            parts.extend(split_oversized_paragraph(paragraph, limit))
    merged: list[str] = []
    current = ""
    for part in parts:
        if len(current) + len(part) + 1 <= limit:
            current = f"{current}\n{part}".strip()
        else:
            if current:
                merged.append(current)
            current = part
    if current:
        merged.append(current)
    return merged or split_hard(content, limit)


def chunk_document(text: str) -> list[dict]:
    chunks: list[dict] = []
    current_heading = "文档说明"
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_lines
        body = "\n".join(current_lines).strip()
        current_lines = []
        if not body:
            return
        content = body
        if current_heading != "文档说明":
            content = f"{current_heading}\n{body}"
        for piece in split_content(content, MAX_CHUNK_CHARS):
            chunks.append(
                {
                    "heading": current_heading,
                    "content": piece,
                }
            )

    for line in text.splitlines():
        match = HEADING_PATTERN.match(line)
        if match:
            flush()
            current_heading = match.group(1).strip()
        else:
            current_lines.append(line)
    flush()
    return chunks


def build_document(row: dict, path: Path) -> Document:
    raw = read_text(path)
    comment_meta = parse_metadata_comment(raw)
    text = strip_metadata_and_frontmatter(raw)
    doc = Document(
        doc_id=row.get("文档编号") or comment_meta.get("doc_id") or path.stem,
        title=extract_title(text, raw)
        or row.get("文件名", path.name),
        filename=row.get("文件名", path.name),
        category=row.get("类别") or comment_meta.get("category") or "其他",
        source=row.get("来源") or comment_meta.get("source") or "",
        method=row.get("获取方式") or comment_meta.get("method") or "",
        update_date=row.get("更新日期") or comment_meta.get("update_date") or "",
        permission=row.get("权限级别") or comment_meta.get("permission") or "全员",
        owner=row.get("负责人") or comment_meta.get("owner") or "",
        status=row.get("状态") or comment_meta.get("status") or "已清洗",
        remark=row.get("备注") or comment_meta.get("remark") or "",
        source_url=row.get("原始来源URL", ""),
        license=row.get("许可证", ""),
        file_path=str(path),
    )
    for index, item in enumerate(chunk_document(text)):
        doc.chunks.append(
            Chunk(
                chunk_index=index,
                heading=item["heading"],
                content=item["content"],
                char_count=len(item["content"]),
            )
        )
    return doc


def import_clean_docs() -> dict:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"manifest not found: {MANIFEST_PATH}")
    if not CLEAN_DIR.exists():
        raise FileNotFoundError(f"clean dir not found: {CLEAN_DIR}")

    init_db()
    db = SessionLocal()
    imported = 0
    chunk_total = 0
    by_category = {}
    skipped = []

    try:
        with MANIFEST_PATH.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))

        for row in rows:
            rel = row.get("文件名", "")
            if not rel:
                skipped.append(row.get("文档编号", "?"))
                continue
            path = (CLEAN_DIR / rel).resolve()
            if not path.is_file():
                skipped.append(f"{row.get('文档编号')}: {rel}")
                continue

            doc = build_document(row, path)
            existing = (
                db.query(Document).filter(Document.doc_id == doc.doc_id).first()
            )
            if existing:
                db.delete(existing)
                db.flush()

            db.add(doc)
            db.commit()
            imported += 1
            chunk_total += len(doc.chunks)
            by_category[doc.category] = by_category.get(doc.category, 0) + 1
    finally:
        db.close()

    result = {
        "documents": imported,
        "chunks": chunk_total,
        "by_category": by_category,
        "skipped": skipped,
    }
    print(result)
    return result


if __name__ == "__main__":
    import_clean_docs()


