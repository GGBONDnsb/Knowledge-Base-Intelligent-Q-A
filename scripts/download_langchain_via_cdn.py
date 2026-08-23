"""Download LangChain docs through jsDelivr without GitHub API calls."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

from download_technical_docs import LANGCHAIN_FILES


OUTPUT_ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    os.environ.get("DATA_ROOT", r"D:\Codex\数据")
)
RAW = OUTPUT_ROOT / "data" / "raw" / "technical" / "langchain"
META = OUTPUT_ROOT / "data" / "meta"


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    META.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for source_path in LANGCHAIN_FILES:
        rel = source_path[len("src/oss/") :]
        url = f"https://cdn.jsdelivr.net/gh/langchain-ai/docs@main/{source_path}"
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        dest = RAW / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        downloaded.append(
            {
                "filename": rel,
                "source_path": source_path,
                "source_url": (
                    "https://github.com/langchain-ai/docs/blob/main/" + source_path
                ),
            }
        )
    manifest = {
        "project": "langchain",
        "repo": "langchain-ai/docs",
        "ref": "main",
        "commit": "",
        "license": "MIT",
        "license_url": "https://github.com/langchain-ai/docs/blob/main/LICENSE",
        "updated_at": "",
        "download_date": "2026-08-18",
        "source_base": "https://github.com/langchain-ai/docs/tree/main",
        "files": downloaded,
    }
    (META / "downloaded_langchain.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"langchain: {len(downloaded)}")


if __name__ == "__main__":
    main()
