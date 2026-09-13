from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from app.agent_service import pending_store, run_agent
from app.config import DEEPSEEK_API_KEY
from app.database import SessionLocal, init_db
from app.interview_data_import import reset_interview_data

QUESTIONS_PATH = Path(__file__).resolve().parent / "agent_questions.json"
RESULTS_PATH = Path(__file__).resolve().parent / "agent_results.json"
REPORT_PATH = Path(__file__).resolve().parent / "agent_report.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Agent task-level eval")
    parser.add_argument("--limit", type=int, default=0, help="只执行前 N 条")
    args = parser.parse_args()

    if not DEEPSEEK_API_KEY:
        print("未配置 DEEPSEEK_API_KEY，无法执行 Agent 评测")
        return
    init_db()
    db = SessionLocal()
    try:
        reset_interview_data(db)
    finally:
        db.close()
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    if args.limit > 0:
        questions = questions[: args.limit]

    rows: list[dict] = []
    for question in questions:
        started = time.perf_counter()
        try:
            result = run_agent(
                message=question["prompt"],
                employee_id=question["employee_id"],
                role=question["role"],
            )
            tools_used = result.tools_used
            pending = result.pending_action is not None
            answer = result.answer
            error = ""
        except Exception as exc:
            tools_used = []
            pending = False
            answer = ""
            error = f"{type(exc).__name__}: {exc}"
            result = None

        required_ok = bool(result) and all(
            tool in tools_used for tool in question["required_tools"]
        )
        forbidden_ok = all(
            tool not in tools_used
            for tool in question.get("forbidden_tools", [])
        )
        pending_ok = pending == question["expect_pending"]
        passed = required_ok and forbidden_ok and pending_ok and not error
        rows.append(
            {
                "id": question["id"],
                "prompt": question["prompt"],
                "employee_id": question["employee_id"],
                "role": question["role"],
                "tools_used": tools_used,
                "required_ok": required_ok,
                "forbidden_ok": forbidden_ok,
                "pending_ok": pending_ok,
                "passed": passed,
                "answer": answer,
                "pending_action": (
                    result.pending_action.action_id
                    if result and result.pending_action
                    else None
                ),
                "elapsed_ms": round(
                    (time.perf_counter() - started) * 1000, 2
                ),
                "error": error,
            }
        )
        if result is not None and result.pending_action is not None:
            pending_store.cancel(result.pending_action.action_id)
        print(
            f"{question['id']} {'PASS' if passed else 'FAIL'} | "
            f"tools={','.join(tools_used) or '-'}"
        )
        time.sleep(0.2)

    passed = sum(1 for row in rows if row["passed"])
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(rows),
        "passed": passed,
        "pass_rate": round(passed / len(rows), 4) if rows else 0.0,
        "rows": rows,
    }
    RESULTS_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Agent 任务评测报告",
        "",
        f"- 生成时间：{summary['generated_at']}",
        f"- 任务总数：{len(rows)}",
        f"- 通过数：{passed}",
        f"- 通过率：{summary['pass_rate'] * 100:.1f}%",
        "",
        "| 编号 | 结果 | 必需工具 | 越权检查 | 待确认检查 | 耗时(ms) | 工具调用 |",
        "| --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| {id} | {result} | {required} | {forbidden} | {pending} | "
            "{elapsed} | {tools} |".format(
                id=row["id"],
                result="PASS" if row["passed"] else "FAIL",
                required="PASS" if row["required_ok"] else "FAIL",
                forbidden="PASS" if row["forbidden_ok"] else "FAIL",
                pending="PASS" if row["pending_ok"] else "FAIL",
                elapsed=row["elapsed_ms"],
                tools=", ".join(row["tools_used"]) or "-",
            )
        )
    failures = [row for row in rows if not row["passed"]]
    if failures:
        lines.extend(["", "## 失败案例", ""])
        for row in failures:
            lines.extend(
                [
                    f"### {row['id']}",
                    "",
                    f"- 问题：{row['prompt']}",
                    f"- 工具调用：{', '.join(row['tools_used']) or '-'}",
                    f"- 错误：{row['error'] or '-'}",
                    f"- 回答：{row['answer'] or '-'}",
                    "",
                ]
            )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nAgent 评测：{passed}/{len(rows)} 通过")
    print(f"结果：{RESULTS_PATH}")
    print(f"报告：{REPORT_PATH}")


if __name__ == "__main__":
    main()
