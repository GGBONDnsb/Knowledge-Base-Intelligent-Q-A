"""Download PostgreSQL official docs and convert them to Markdown."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from download_technical_docs import POSTGRESQL_PAGES, HEADERS, html_to_markdown


OUTPUT_ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    os.environ.get("DATA_ROOT", r"D:\Codex\数据")
)
RAW = OUTPUT_ROOT / "data" / "raw" / "technical" / "postgresql"
META = OUTPUT_ROOT / "data" / "meta"


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    META.mkdir(parents=True, exist_ok=True)
    base = "https://www.postgresql.org/docs/current/"
    downloaded = []
    missing = []
    for slug, title in POSTGRESQL_PAGES:
        url = base + slug + ".html"
        resp = requests.get(url, headers=HEADERS, timeout=120)
        if resp.status_code != 200:
            missing.append(f"{slug} (HTTP {resp.status_code})")
            continue
        markdown = html_to_markdown(resp.text)
        if not markdown:
            missing.append(f"{slug} (empty conversion)")
            continue
        dest = RAW / f"{slug}.md"
        dest.write_text(markdown, encoding="utf-8")
        soup = BeautifulSoup(resp.text, "html.parser")
        page_title = soup.title.string.strip() if soup.title and soup.title.string else title
        downloaded.append(
            {
                "filename": f"{slug}.md",
                "source_path": f"{slug}.html",
                "source_url": url,
                "title": page_title,
            }
        )
    manifest = {
        "project": "postgresql",
        "repo": "",
        "ref": "current",
        "commit": "",
        "license": "PostgreSQL License",
        "license_url": "https://www.postgresql.org/about/licence/",
        "updated_at": "2026-08-18",
        "download_date": "2026-08-18",
        "source_base": base,
        "files": downloaded,
    }
    (META / "downloaded_postgresql.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"postgresql: {len(downloaded)} downloaded, {len(missing)} missing")
    for item in missing:
        print(f"  - {item}")


if __name__ == "__main__":
    main()
