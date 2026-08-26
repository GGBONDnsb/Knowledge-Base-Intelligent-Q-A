from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from app import retrieval

EVAL_DIR = Path(__file__).resolve().parent
QUESTIONS_PATH = EVAL_DIR / "questions.json"
TOP_K = 5

MODE = sys.argv[1] if len(sys.argv) > 1 else "hybrid"


def rate_text(hit_count: int, total: int) -> str:
    if not total:
        return "0%"
    return f"{hit_count / total * 100:.1f}%"


def main() -> None:
    if MODE == "bm25":
        from app.retrieval import BM25Index

        index = BM25Index()
        index.load()
        search = index.search
        suffix = "bm25"
        title = "BM25 基线评测报告"
    else:
        index = retrieval.build_index()
        search = index.search
        suffix = "hybrid"
        title = "混合检索评测报告"

    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    results_path = EVAL_DIR / f"results_{suffix}.json"
    report_path = EVAL_DIR / f"report_{suffix}.md"

    results = []
    category_hit = defaultdict(lambda: [0, 0])
    difficulty_hit = defaultdict(lambda: [0, 0])

    for item in questions:
        hits = search(item["question"], top_k=TOP_K)
        retrieved_ids = [hit["doc_id"] for hit in hits]
        expected = item["expected_doc_ids"]
        passed = any(doc_id in retrieved_ids for doc_id in expected)

        results.append(
            {
                "id": item["id"],
                "question": item["question"],
                "category": item["category"],
                "difficulty": item["difficulty"],
                "expected_doc_ids": expected,
                "retrieved_doc_ids": retrieved_ids,
                "passed": passed,
            }
        )
        category_hit[item["category"]][0] += 1
        category_hit[item["category"]][1] += int(passed)
        difficulty_hit[item["difficulty"]][0] += 1
        difficulty_hit[item["difficulty"]][1] += int(passed)

    total = len(results)
    passed_total = sum(1 for item in results if item["passed"])

    payload = {
        "mode": suffix,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "top_k": TOP_K,
        "total": total,
        "passed": passed_total,
        "hit_rate": rate_text(passed_total, total),
        "results": results,
    }
    results_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        f"# {title}",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 评测题数：{total}",
        f"- 命中数：{passed_total}",
        f"- Hit@5：{payload['hit_rate']}",
        "",
        "## 分类命中率",
        "",
        "| 类别 | 命中 / 总数 | 命中率 |",
        "| --- | --- | --- |",
    ]
    for category in ("制度类", "产品资料类", "技术文档类"):
        total_c, hit_c = category_hit[category]
        lines.append(f"| {category} | {hit_c} / {total_c} | {rate_text(hit_c, total_c)} |")

    lines.extend(
        [
            "",
            "## 难度命中率",
            "",
            "| 难度 | 命中 / 总数 | 命中率 |",
            "| --- | --- | --- |",
        ]
    )
    for difficulty in ("简单", "中等", "难"):
        total_d, hit_d = difficulty_hit[difficulty]
        lines.append(
            f"| {difficulty} | {hit_d} / {total_d} | {rate_text(hit_d, total_d)} |"
        )

    failed = [item for item in results if not item["passed"]]
    lines.extend(
        [
            "",
            "## 未命中题目",
            "",
            "| 编号 | 问题 | 预期文档 | 实际返回 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for item in failed:
        lines.append(
            f"| {item['id']} | {item['question']} | "
            f"{', '.join(item['expected_doc_ids'])} | "
            f"{', '.join(item['retrieved_doc_ids']) or '无' } |"
        )

    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"- 整体 Hit@5 为 {payload['hit_rate']}，共 {len(failed)} 道未命中。",
        ]
    )
    if failed:
        lines.append(f"- 最典型失败题：{failed[0]['id']}，问题“{failed[0]['question']}”。")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"mode={suffix} total={total} passed={passed_total} hit_rate={payload['hit_rate']}")
    for category in ("制度类", "产品资料类", "技术文档类"):
        total_c, hit_c = category_hit[category]
        print(f"{category}: {hit_c}/{total_c} {rate_text(hit_c, total_c)}")


if __name__ == "__main__":
    main()
