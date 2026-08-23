"""Download public technical documentation for the demo knowledge base.

Sources:
- GitHub raw Markdown files from FastAPI, Redis, Docker, and LangChain docs.
- PostgreSQL official HTML docs converted to Markdown.

All files are public documentation used for learning and portfolio purposes.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString


OUTPUT_ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    os.environ.get("DATA_ROOT", r"D:\Codex\数据")
)
RAW_TECH = OUTPUT_ROOT / "data" / "raw" / "technical"
META_DIR = OUTPUT_ROOT / "data" / "meta"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def api_get(url: str, *, retries: int = 3) -> dict:
    for attempt in range(retries):
        resp = requests.get(url, headers=HEADERS, timeout=60)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 403 and attempt < retries - 1:
            time.sleep(2 * (attempt + 1))
            continue
        resp.raise_for_status()
    raise RuntimeError(f"failed to fetch {url}")


def get_repo_info(repo: str) -> dict:
    data = api_get(f"https://api.github.com/repos/{repo}")
    return {
        "repo": repo,
        "default_branch": data.get("default_branch", "main"),
        "license": (data.get("license") or {}).get("spdx_id") or "未知",
        "license_url": (data.get("license") or {}).get("html_url") or "",
        "updated_at": data.get("updated_at", ""),
    }


def get_tree(repo: str, ref: str) -> dict[str, str]:
    data = api_get(f"https://api.github.com/repos/{repo}/git/trees/{ref}?recursive=1")
    return {item["path"]: item["type"] for item in data.get("tree", [])}


def get_commit(repo: str, ref: str) -> str:
    data = api_get(f"https://api.github.com/repos/{repo}/commits/{ref}")
    return data.get("sha", "")


def raw_download(repo: str, ref: str, path: str) -> bytes:
    """Fetch a file through jsDelivr's GitHub CDN.

    raw.githubusercontent.com is unreachable in this network environment, so the
    CDN is used instead. The returned content is the same public file.
    """
    url = f"https://cdn.jsdelivr.net/gh/{repo}@{ref}/{path}"
    resp = requests.get(url, headers=HEADERS, timeout=120)
    resp.raise_for_status()
    return resp.content


def save_bytes(dest: Path, content: bytes) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)


def target_rel(source_path: str, strip_prefix: str | None) -> str:
    rel = source_path
    if strip_prefix and rel.startswith(strip_prefix + "/"):
        rel = rel[len(strip_prefix) + 1 :]
    return rel


def download_github_project(
    project: str,
    repo: str,
    ref: str,
    files: list[str],
    strip_prefix: str | None,
) -> list[dict]:
    info = get_repo_info(repo)
    tree = get_tree(repo, ref)
    commit = get_commit(repo, ref)
    target_dir = RAW_TECH / project
    target_dir.mkdir(parents=True, exist_ok=True)

    downloaded = []
    missing = []
    for source_path in files:
        if tree.get(source_path) != "blob":
            missing.append(source_path)
            continue
        rel = target_rel(source_path, strip_prefix)
        dest = target_dir / rel
        try:
            content = raw_download(repo, ref, source_path)
            save_bytes(dest, content)
            downloaded.append(
                {
                    "filename": rel,
                    "source_path": source_path,
                    "source_url": (
                        f"https://github.com/{repo}/blob/{ref}/{source_path}"
                    ),
                }
            )
        except requests.RequestException as exc:
            missing.append(f"{source_path} ({exc})")
        except (FileNotFoundError, OSError) as exc:
            missing.append(f"{source_path} ({exc})")

    manifest = {
        "project": project,
        "repo": repo,
        "ref": ref,
        "commit": commit,
        "license": info["license"],
        "license_url": info["license_url"],
        "updated_at": info["updated_at"],
        "download_date": "2026-08-18",
        "source_base": f"https://github.com/{repo}/tree/{ref}",
        "files": downloaded,
    }
    (META_DIR / f"downloaded_{project}.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[{project}] downloaded {len(downloaded)}, missing {len(missing)}")
    if missing:
        print("\n".join(f"  - {item}" for item in missing))
    return downloaded


def inline_text(node) -> str:
    if isinstance(node, NavigableString):
        return str(node)
    if node is None or node.name is None:
        return ""
    name = node.name
    if name == "br":
        return "\n"
    if name in ("b", "strong"):
        return "**" + "".join(inline_text(c) for c in node.children) + "**"
    if name in ("i", "em"):
        return "*" + "".join(inline_text(c) for c in node.children) + "*"
    if name == "code":
        return "`" + node.get_text(" ", strip=True) + "`"
    if name == "a":
        href = node.get("href", "")
        if href.startswith("/docs/"):
            href = "https://www.postgresql.org" + href
        label = "".join(inline_text(c) for c in node.children).strip()
        return f"[{label}]({href})" if label else ""
    if name in ("sup", "sub"):
        return ""
    if name in (
        "span",
        "abbr",
        "acronym",
        "tt",
        "var",
        "samp",
        "dfn",
        "cite",
    ):
        return "".join(inline_text(c) for c in node.children)
    return "".join(inline_text(c) for c in node.children)


def process_list(node, depth: int = 0) -> list[str]:
    lines: list[str] = []
    ordered = node.name == "ol"
    number = 1
    for li in node.find_all("li", recursive=False):
        prefix = f"{number}. " if ordered else "- "
        text = re.sub(r"\s+", " ", inline_text(li)).strip()
        lines.append("  " * depth + prefix + text)
        if ordered:
            number += 1
        for child in li.find_all(["ul", "ol"], recursive=False):
            lines.extend(process_list(child, depth + 1))
    return lines


def process_table(node) -> list[str]:
    rows = []
    for tr in node.find_all("tr"):
        cells = [
            re.sub(r"\s+", " ", inline_text(cell)).strip()
            for cell in tr.find_all(["th", "td"])
        ]
        if cells:
            rows.append("| " + " | ".join(cells) + " |")
    if not rows:
        return []
    output = [rows[0], "| --- " * len(rows[0].split("|")[1:-1]) + "|"]
    output.extend(rows[1:])
    return output


def process_block(node) -> list[str]:
    if node is None or isinstance(node, NavigableString):
        return []
    name = node.name
    if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(name[1])
        return [f"{'#' * level} {re.sub(r'\\s+', ' ', inline_text(node)).strip()}", ""]
    if name == "p":
        return [re.sub(r"\s+", " ", inline_text(node)).strip(), ""]
    if name in ("ul", "ol"):
        return process_list(node) + [""]
    if name == "pre":
        return ["```", node.get_text().strip("\n"), "```", ""]
    if name == "table":
        return process_table(node) + [""]
    if name == "blockquote":
        text = re.sub(r"\s+", " ", inline_text(node)).strip()
        return [f"> {text}", ""]
    if name in ("dl",):
        lines = []
        for dt in node.find_all("dt"):
            dd = dt.find_next_sibling("dd")
            term = re.sub(r"\s+", " ", inline_text(dt)).strip()
            desc = re.sub(r"\s+", " ", inline_text(dd)).strip() if dd else ""
            lines.append(f"- **{term}**：{desc}")
        lines.append("")
        return lines
    if name in ("div", "section", "article", "main", "body", "a"):
        lines = []
        for child in node.children:
            lines.extend(process_block(child))
        return lines
    return []


def html_to_markdown(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("#docContent") or soup.select_one("article") or soup.body
    if content is None:
        return ""
    for selector in ("#docComments", ".navfooter", ".navheader", ".breadcrumbs"):
        for el in content.select(selector):
            el.decompose()

    blocks = []
    for child in content.children:
        blocks.extend(process_block(child))
    text = "\n".join(blocks)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


POSTGRESQL_PAGES = [
    ("tutorial", "入门教程"),
    ("tutorial-createdb", "创建数据库"),
    ("tutorial-select", "查询数据"),
    ("tutorial-join", "表连接"),
    ("tutorial-advanced", "高级特性"),
    ("tutorial-window", "窗口函数"),
    ("ddl", "数据定义"),
    ("ddl-basics", "表基础"),
    ("ddl-constraints", "约束"),
    ("ddl-partitioning", "分区"),
    ("queries", "查询"),
    ("queries-select-lists", "SELECT 列表"),
    ("queries-table-expressions", "表表达式"),
    ("queries-with", "WITH 查询"),
    ("queries-limit", "LIMIT 与 OFFSET"),
    ("sql-select", "SELECT 语句"),
    ("sql-insert", "INSERT 语句"),
    ("sql-update", "UPDATE 语句"),
    ("sql-delete", "DELETE 语句"),
    ("sql-createindex", "CREATE INDEX"),
    ("sql-createtable", "CREATE TABLE"),
    ("sql-altertable", "ALTER TABLE"),
    ("indexes", "索引"),
    ("indexes-types", "索引类型"),
    ("indexes-ordering", "索引排序"),
    ("functions-string", "字符串函数"),
    ("functions-datetime", "日期时间函数"),
    ("functions-aggregate", "聚合函数"),
    ("functions-window", "窗口函数"),
    ("transactions", "事务"),
    ("mvcc", "并发控制"),
    ("routine-vacuuming", "VACUUM"),
    ("backup", "备份与恢复"),
    ("wal", "预写日志"),
    ("logical-replication", "逻辑复制"),
    ("high-availability", "高可用"),
    ("monitoring", "监控"),
    ("runtime-config-resource", "资源消耗配置"),
    ("performance-tips", "性能提示"),
    ("client-authentication", "客户端认证"),
    ("auth-pg-hba-conf", "pg_hba.conf"),
]


def download_postgresql() -> list[dict]:
    project = "postgresql"
    target_dir = RAW_TECH / project
    target_dir.mkdir(parents=True, exist_ok=True)
    base = "https://www.postgresql.org/docs/current/"
    downloaded = []
    missing = []
    for slug, title in POSTGRESQL_PAGES:
        url = base + slug + ".html"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=120)
            if resp.status_code != 200:
                missing.append(f"{slug} (HTTP {resp.status_code})")
                continue
            markdown = html_to_markdown(resp.text)
            if not markdown:
                missing.append(f"{slug} (empty conversion)")
                continue
            dest = target_dir / f"{slug}.md"
            dest.write_text(markdown, encoding="utf-8")
            page_title = title
            soup = BeautifulSoup(resp.text, "html.parser")
            if soup.title and soup.title.string:
                page_title = soup.title.string.strip()
            downloaded.append(
                {
                    "filename": f"{slug}.md",
                    "source_path": f"{slug}.html",
                    "source_url": url,
                    "title": page_title,
                }
            )
        except requests.RequestException as exc:
            missing.append(f"{slug} ({exc})")

    manifest = {
        "project": project,
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
    (META_DIR / f"downloaded_{project}.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[postgresql] downloaded {len(downloaded)}, missing {len(missing)}")
    if missing:
        print("\n".join(f"  - {item}" for item in missing))
    return downloaded


FASTAPI_FILES = [
    "features.md",
    "async.md",
    "alternatives.md",
    "tutorial/first-steps.md",
    "tutorial/path-params.md",
    "tutorial/query-params.md",
    "tutorial/body.md",
    "tutorial/body-updates.md",
    "tutorial/query-params-str-validations.md",
    "tutorial/path-params-numeric-validations.md",
    "tutorial/response-model.md",
    "tutorial/extra-models.md",
    "tutorial/handling-errors.md",
    "tutorial/request-files.md",
    "tutorial/sql-databases.md",
    "tutorial/dependencies/index.md",
    "tutorial/security/first-steps.md",
    "tutorial/security/oauth2-jwt.md",
    "tutorial/testing.md",
    "tutorial/cors.md",
    "tutorial/middleware.md",
    "tutorial/static-files.md",
    "tutorial/background-tasks.md",
    "advanced/websockets.md",
    "advanced/middleware.md",
    "advanced/events.md",
    "advanced/async-tests.md",
    "advanced/behind-a-proxy.md",
    "advanced/generate-clients.md",
    "advanced/testing-dependencies.md",
    "deployment/index.md",
    "deployment/docker.md",
    "deployment/versions.md",
]

REDIS_FILES = [
    "docs/get-started/data-store.md",
    "docs/get-started/faq.md",
    "docs/data-types/strings.md",
    "docs/data-types/lists.md",
    "docs/data-types/sets.md",
    "docs/data-types/hashes.md",
    "docs/data-types/sorted-sets.md",
    "docs/data-types/streams.md",
    "docs/data-types/bitmaps.md",
    "docs/data-types/bitfields.md",
    "docs/data-types/geospatial.md",
    "docs/connect/cli.md",
    "docs/connect/clients/python.md",
    "docs/connect/clients/java/lettuce.md",
    "docs/connect/clients/go.md",
    "docs/interact/transactions.md",
    "docs/interact/pubsub.md",
    "docs/interact/programmability/eval-intro.md",
    "docs/interact/programmability/functions-intro.md",
    "docs/interact/programmability/lua-api.md",
    "docs/manual/keyspace.md",
    "docs/manual/keyspace-notifications.md",
    "docs/manual/client-side-caching.md",
    "docs/manual/patterns/distributed-locks.md",
    "docs/manual/pipelining/index.md",
    "docs/management/persistence.md",
    "docs/management/replication.md",
    "docs/management/sentinel.md",
    "docs/management/security/acl.md",
    "docs/management/security/encryption.md",
    "docs/management/optimization/memory-optimization.md",
    "docs/management/optimization/latency.md",
    "docs/management/config.md",
    "docs/reference/protocol-spec.md",
    "docs/reference/eviction/index.md",
    "docs/reference/cluster-spec.md",
]

DOCKER_FILES = [
    "content/get-started/docker-overview.md",
    "content/get-started/get-docker.md",
    "content/get-started/docker-concepts/the-basics/what-is-a-container.md",
    "content/get-started/docker-concepts/the-basics/what-is-an-image.md",
    "content/get-started/docker-concepts/the-basics/what-is-a-registry.md",
    "content/get-started/docker-concepts/the-basics/what-is-docker-compose.md",
    "content/get-started/docker-concepts/building-images/writing-a-dockerfile.md",
    "content/get-started/docker-concepts/building-images/multi-stage-builds.md",
    "content/get-started/docker-concepts/building-images/using-the-build-cache.md",
    "content/get-started/docker-concepts/building-images/understanding-image-layers.md",
    "content/get-started/docker-concepts/building-images/build-tag-and-publish-an-image.md",
    "content/get-started/docker-concepts/running-containers/publishing-ports.md",
    "content/get-started/docker-concepts/running-containers/persisting-container-data.md",
    "content/get-started/docker-concepts/running-containers/sharing-local-files.md",
    "content/get-started/docker-concepts/running-containers/overriding-container-defaults.md",
    "content/get-started/docker-concepts/running-containers/multi-container-applications.md",
    "content/get-started/introduction/build-and-push-first-image.md",
    "content/get-started/introduction/develop-with-containers.md",
    "content/get-started/introduction/get-docker-desktop.md",
    "content/get-started/workshop/02_our_app.md",
    "content/get-started/workshop/05_persisting_data.md",
    "content/get-started/workshop/06_bind_mounts.md",
    "content/get-started/workshop/07_multi_container.md",
    "content/get-started/workshop/08_using_compose.md",
    "content/get-started/workshop/09_image_best.md",
    "content/guides/docker-compose.md",
    "content/guides/compose-bake.md",
    "content/guides/databases.md",
    "content/guides/kafka.md",
    "content/guides/go-prometheus-monitoring.md",
    "content/guides/django.md",
    "content/guides/docker-scout.md",
    "content/guides/kube-deploy.md",
    "content/guides/bake.md",
    "content/guides/gha.md",
    "content/guides/azure-pipelines.md",
    "content/guides/container-supported-development.md",
    "content/guides/agentic-ai.md",
]

LANGCHAIN_FILES = [
    "src/oss/concepts/context.mdx",
    "src/oss/concepts/memory.mdx",
    "src/oss/concepts/providers-and-models.mdx",
    "src/oss/langchain/overview.mdx",
    "src/oss/langchain/quickstart.mdx",
    "src/oss/langchain/install.mdx",
    "src/oss/langchain/agents.mdx",
    "src/oss/langchain/models.mdx",
    "src/oss/langchain/messages.mdx",
    "src/oss/langchain/tools.mdx",
    "src/oss/langchain/retrieval.mdx",
    "src/oss/langchain/knowledge-base.mdx",
    "src/oss/langchain/structured-output.mdx",
    "src/oss/langchain/streaming.mdx",
    "src/oss/langchain/human-in-the-loop.mdx",
    "src/oss/langchain/observability.mdx",
    "src/oss/langchain/event-streaming.mdx",
    "src/oss/langchain/mcp.mdx",
    "src/oss/langchain/middleware/overview.mdx",
    "src/oss/langchain/multi-agent/index.mdx",
    "src/oss/langchain/multi-agent/subagents.mdx",
    "src/oss/langchain/test/evals.mdx",
    "src/oss/langgraph/overview.mdx",
    "src/oss/langgraph/quickstart.mdx",
    "src/oss/langgraph/graph-api.mdx",
    "src/oss/langgraph/functional-api.mdx",
    "src/oss/langgraph/agentic-rag.mdx",
    "src/oss/langgraph/persistence.mdx",
    "src/oss/langgraph/streaming.mdx",
    "src/oss/langgraph/deploy.mdx",
]


def main() -> None:
    META_DIR.mkdir(parents=True, exist_ok=True)
    download_github_project(
        "fastapi",
        "fastapi/fastapi",
        "master",
        [f"docs/en/docs/{item}" for item in FASTAPI_FILES],
        "docs/en/docs",
    )
    download_github_project(
        "redis",
        "redis/redis-doc",
        "master",
        REDIS_FILES,
        None,
    )
    download_github_project(
        "docker",
        "docker/docs",
        "main",
        DOCKER_FILES,
        "content",
    )
    download_github_project(
        "langchain",
        "langchain-ai/docs",
        "main",
        LANGCHAIN_FILES,
        "src/oss",
    )
    download_postgresql()


if __name__ == "__main__":
    main()
