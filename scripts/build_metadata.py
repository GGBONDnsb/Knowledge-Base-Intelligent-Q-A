"""Build the final metadata manifest and source documentation."""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path


OUTPUT_ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    os.environ.get("DATA_ROOT", r"D:\Codex\数据")
)
META_DIR = OUTPUT_ROOT / "data" / "meta"

HEADERS = [
    "文档编号",
    "文件名",
    "类别",
    "来源",
    "获取方式",
    "更新日期",
    "权限级别",
    "负责人",
    "状态",
    "备注",
    "原始来源URL",
    "许可证",
]


def rows_from_generated() -> list[dict]:
    rows = []
    for name, category in (
        ("generated_institutional.json", "制度类"),
        ("generated_products.json", "产品资料类"),
    ):
        path = META_DIR / name
        if not path.exists():
            continue
        entries = json.loads(path.read_text(encoding="utf-8"))
        for entry in entries:
            folder = "institutional" if category == "制度类" else "products"
            rows.append(
                {
                    "文档编号": entry["doc_id"],
                    "文件名": f"{folder}/{entry['filename']}",
                    "类别": category,
                    "来源": entry["source"],
                    "获取方式": entry["method"],
                    "更新日期": entry["update_date"],
                    "权限级别": entry["permission"],
                    "负责人": entry["owner"],
                    "状态": "已清洗",
                    "备注": entry["remark"],
                    "原始来源URL": "",
                    "许可证": "自编模拟文档",
                }
            )
    return rows


def rows_from_technical() -> list[dict]:
    rows = []
    for path in sorted(META_DIR.glob("downloaded_*.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        project = manifest["project"]
        for index, entry in enumerate(manifest["files"], start=1):
            clean_name = entry["filename"].replace(".mdx", ".md")
            rows.append(
                {
                    "文档编号": f"YQ-TECH-{project.upper()}-{index:03d}",
                    "文件名": f"technical/{project}/{clean_name}",
                    "类别": "技术文档类",
                    "来源": f"{project} 官方文档",
                    "获取方式": "GitHub/官网下载",
                    "更新日期": manifest.get("download_date", "2026-08-18"),
                    "权限级别": "全员",
                    "负责人": "资料管理组",
                    "状态": "已清洗",
                    "备注": entry.get("title", ""),
                    "原始来源URL": entry.get("source_url", ""),
                    "许可证": manifest.get("license", ""),
                }
            )
    return rows


def write_manifest(rows: list[dict]) -> None:
    path = META_DIR / "manifest.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def write_sources(rows: list[dict]) -> None:
    counts = Counter(row["类别"] for row in rows)
    lines = [
        "# 数据来源说明",
        "",
        "本数据集仅用于企业智能知识库问答系统的学习演示和求职作品，不包含任何真实企业的机密或隐私数据。",
        "",
        "## 1. 汇总",
        "",
        "| 类别 | 文档数 |",
        "| --- | --- |",
    ]
    for category in ("制度类", "产品资料类", "技术文档类"):
        lines.append(f"| {category} | {counts.get(category, 0)} |")
    lines.extend(
        [
            f"| 合计 | {len(rows)} |",
            "",
            "## 2. 自编模拟文档",
            "",
            "- 制度类：30 份，由云启科技模拟编写，标准答案可控，适合建立评测集。",
            "- 产品资料类：25 份，参考开源项目公开功能后重新编写，不直接复制原文。",
            "- 所有模拟文档均标注“模拟文档，仅用于学习演示”。",
            "",
            "## 3. 开源项目文档",
            "",
            "| 项目 | 文档数 | 许可证 | 来源 |",
            "| --- | --- | --- | --- |",
        ]
    )
    project_rows = sorted(
        {
            (row["文件名"].split("/")[1] if "/" in row["文件名"] else "")
            for row in rows
            if row["类别"] == "技术文档类"
        }
    )
    tech_meta = {}
    for path in META_DIR.glob("downloaded_*.json"):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        tech_meta[manifest["project"]] = manifest
    for project in project_rows:
        meta = tech_meta.get(project, {})
        count = sum(
            1
            for row in rows
            if row["类别"] == "技术文档类"
            and row["文件名"].startswith(f"technical/{project}/")
        )
        license_name = meta.get("license", "以仓库 LICENSE 为准")
        base = meta.get("source_base", f"https://github.com/")
        lines.append(f"| {project} | {count} | {license_name} | {base} |")
    lines.extend(
        [
            "",
            "## 4. 合规说明",
            "",
            "- 只使用公开资料和自编模拟文档，保留每个来源的出处。",
            "- 开源文档保留原仓库许可证，未修改版权声明。",
            "- 若用于公开演示，建议在 README 中说明数据用途与来源。",
            "",
        ]
    )
    (META_DIR / "sources.md").write_text("\n".join(lines), encoding="utf-8")


def write_cleaning_log() -> None:
    log_path = META_DIR / "cleaning_log.json"
    if not log_path.exists():
        return
    log = json.loads(log_path.read_text(encoding="utf-8"))
    issues = Counter()
    for item in log:
        for issue in item["issues"]:
            issues[issue] += 1
    lines = [
        "# 数据清洗日志",
        "",
        "清洗范围：统一换行、压缩空行、合并表格空行；MDX 转 Markdown；PostgreSQL 页面移除目录。",
        "",
        "## 处理统计",
        "",
        f"- 处理文档数：{len(log)}",
        "",
        "| 处理项 | 文档数 |",
        "| --- | --- |",
    ]
    for issue, count in issues.most_common():
        lines.append(f"| {issue} | {count} |")
    lines.extend(
        [
            "",
            "## 面试素材：清洗中遇到的问题",
            "",
            "1. GitHub 文档格式不统一：Markdown、MDX、HTML 混用，统一转换为 Markdown 并移除 JSX/frontmatter。",
            "2. PostgreSQL 官方文档为 HTML，需提取正文并转换为 Markdown，同时移除页面目录和导航链接。",
            "3. 表格在生成脚本中行间有空行，清洗时自动合并，保证 Markdown 表格可被解析器正确识别。",
            "4. 网络环境无法访问 raw.githubusercontent.com，改用 jsDelivr CDN 下载相同公开文件，并在元数据中保留原始仓库地址。",
            "",
        ]
    )
    (META_DIR / "cleaning_log.md").write_text("\n".join(lines), encoding="utf-8")


def write_data_readme(rows: list[dict]) -> None:
    counts = Counter(row["类别"] for row in rows)
    lines = [
        "# 云启科技知识库数据集",
        "",
        "本数据集用于企业智能知识库问答系统演示与求职作品，仅限学习用途。",
        "",
        "## 目录结构",
        "",
        "```text",
        "data/",
        "  raw/             原始文件（自编文档、开源文档、转换前 HTML 对应的 Markdown）",
        "    institutional/ 模拟制度 30 份",
        "    products/      模拟产品资料 25 份",
        "    technical/     FastAPI、Redis、Docker、PostgreSQL、LangChain 公开文档",
        "  clean/           清洗后、统一元数据头的 Markdown",
        "  meta/            元数据清单、来源说明、清洗日志",
        "```",
        "",
        "## 当前规模",
        "",
        f"- 制度类：{counts.get('制度类', 0)} 份",
        f"- 产品资料类：{counts.get('产品资料类', 0)} 份",
        f"- 技术文档类：{counts.get('技术文档类', 0)} 份",
        f"- 合计：{len(rows)} 份",
        "",
        "## 使用建议",
        "",
        "1. 先导入 `data/clean` 下的 Markdown 文件。",
        "2. 使用 `data/meta/manifest.csv` 同步文档权限、负责人和来源。",
        "3. 制度类适合建立标准答案评测集，产品资料类适合检索测试，技术文档类适合评测引用准确率。",
        "4. 扩充数据时，按 `data/meta/sources.md` 登记来源和许可证。",
        "",
    ]
    (OUTPUT_ROOT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    rows = rows_from_generated() + rows_from_technical()
    rows.sort(key=lambda row: (row["类别"], row["文档编号"]))
    write_manifest(rows)
    write_sources(rows)
    write_cleaning_log()
    write_data_readme(rows)
    print(f"manifest rows: {len(rows)}")


if __name__ == "__main__":
    main()
