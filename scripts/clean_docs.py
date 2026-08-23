"""Clean raw documents and write normalized Markdown files."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


OUTPUT_ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    os.environ.get("DATA_ROOT", r"D:\Codex\数据")
)
RAW_DIR = OUTPUT_ROOT / "data" / "raw"
CLEAN_DIR = OUTPUT_ROOT / "data" / "clean"
META_DIR = OUTPUT_ROOT / "data" / "meta"


def load_manifests() -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    for path in META_DIR.glob("generated_*.json"):
        for entry in json.loads(path.read_text(encoding="utf-8")):
            category = entry["category"]
            folder = "institutional" if category == "制度类" else "products"
            lookup[f"{folder}/{entry['filename']}"] = entry
    for path in META_DIR.glob("downloaded_*.json"):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        project = manifest["project"]
        for index, entry in enumerate(manifest["files"], start=1):
            key = f"technical/{project}/{entry['filename']}"
            lookup[key] = {
                "doc_id": f"YQ-TECH-{project.upper()}-{index:03d}",
                "filename": entry["filename"],
                "category": "技术文档类",
                "source": f"{project} 官方文档",
                "method": "GitHub/官网下载",
                "update_date": manifest.get("download_date", "2026-08-18"),
                "permission": "全员",
                "owner": "资料管理组",
                "status": "已清洗",
                "remark": entry.get("title", ""),
                "source_url": entry.get("source_url", ""),
                "license": manifest.get("license", ""),
            }
    return lookup


def remove_yaml_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            return text[end + 4 :].lstrip("\n")
    return text


def strip_mdx_syntax(text: str) -> str:
    lines = text.split("\n")
    output = []
    for line in lines:
        stripped = line.strip()
        if re.fullmatch(r":::[a-zA-Z]*", stripped):
            continue
        if re.fullmatch(r"</?[A-Z][A-Za-z]*(?:\s[^>]*)?/?>", stripped):
            continue
        if re.fullmatch(r"\{/\*.*?\*/\}", stripped):
            continue
        if re.fullmatch(r"import\s+.*?from\s+.*", stripped):
            continue
        output.append(line)
    return "\n".join(output)


def remove_postgres_toc(text: str) -> str:
    marker = "**Table of Contents**"
    if marker not in text:
        return text
    start = text.index(marker)
    match = re.search(r"\n#{1,6} ", text[start:])
    if not match:
        return text[:start].rstrip() + "\n"
    return text[:start] + text[start + match.start() :]


def normalize_table_rows(text: str) -> str:
    lines = text.split("\n")
    output = []
    for index, line in enumerate(lines):
        if (
            line.strip() == ""
            and 0 < index < len(lines) - 1
            and lines[index - 1].lstrip().startswith("|")
            and lines[index + 1].lstrip().startswith("|")
        ):
            continue
        output.append(line)
    return "\n".join(output)


def collapse_blank_lines(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def metadata_block(meta: dict) -> str:
    lines = ["<!--", "云启科技知识库文档元数据", ""]
    fields = [
        ("文档编号", "doc_id"),
        ("类别", "category"),
        ("来源", "source"),
        ("获取方式", "method"),
        ("更新日期", "update_date"),
        ("权限级别", "permission"),
        ("负责人", "owner"),
        ("状态", "status"),
    ]
    for label, key in fields:
        lines.append(f"{label}: {meta.get(key, '')}")
    if meta.get("source_url"):
        lines.append(f"原始来源: {meta['source_url']}")
    if meta.get("license"):
        lines.append(f"许可证: {meta['license']}")
    if meta.get("remark"):
        lines.append(f"备注: {meta['remark']}")
    lines.extend(["-->", ""])
    return "\n".join(lines)


def clean_file(src: Path, dst: Path, meta: dict, log: list[dict]) -> None:
    raw = src.read_text(encoding="utf-8", errors="replace")
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    issues = []
    if src.suffix == ".mdx":
        text = remove_yaml_frontmatter(text)
        text = strip_mdx_syntax(text)
        issues.append("MDX 转 Markdown：移除 frontmatter 与 JSX 组件标签")
    if "postgresql" in src.parts:
        before = len(text)
        text = remove_postgres_toc(text)
        if len(text) < before:
            issues.append("PostgreSQL 页面：移除 Table of Contents")
    text = normalize_table_rows(text)
    text = collapse_blank_lines(text)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(metadata_block(meta) + text, encoding="utf-8")
    log.append(
        {
            "doc_id": meta.get("doc_id", ""),
            "raw": str(src.relative_to(RAW_DIR)),
            "clean": str(dst.relative_to(CLEAN_DIR)),
            "issues": issues,
        }
    )


def main() -> None:
    lookup = load_manifests()
    log: list[dict] = []
    count = 0
    for src in sorted(RAW_DIR.rglob("*")):
        if not src.is_file() or src.suffix.lower() not in (".md", ".mdx"):
            continue
        rel = src.relative_to(RAW_DIR)
        meta = lookup.get(rel.as_posix())
        if meta is None:
            meta = {
                "doc_id": rel.stem,
                "filename": rel.name,
                "category": "技术文档类" if "technical" in rel.parts else "其他",
                "source": "未登记",
                "method": "未登记",
                "update_date": "2026-08-18",
                "permission": "全员",
                "owner": "资料管理组",
                "status": "已清洗",
                "remark": "自动生成元数据",
            }
        clean_rel = rel.with_suffix(".md")
        dst = CLEAN_DIR / clean_rel
        clean_file(src, dst, meta, log)
        count += 1

    (META_DIR / "cleaning_log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"cleaned: {count}")


if __name__ == "__main__":
    main()
