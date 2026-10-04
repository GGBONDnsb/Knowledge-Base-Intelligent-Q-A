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
from app.models import AgentAction

QUESTIONS_PATH = Path(__file__).resolve().parent / "agent_questions.json"
RESULTS_PATH = Path(__file__).resolve().parent / "agent_results.json"
REPORT_PATH = Path(__file__).resolve().parent / "agent_report.md"
VALIDATION_PATH = Path(__file__).resolve().parent / "agent_validation.json"


def _pending_exists(session_id: str | None, employee_id: str) -> bool:
    if not session_id:
        return False
    db = SessionLocal()
    try:
        return (
            db.query(AgentAction)
            .filter(
                AgentAction.session_id == session_id,
                AgentAction.employee_id == employee_id,
                AgentAction.status == "待确认",
            )
            .count()
            > 0
        )
    finally:
        db.close()


def _clear_pending(session_id: str | None, employee_id: str) -> None:
    if not session_id:
        return
    db = SessionLocal()
    try:
        action_ids = [
            action_id
            for action_id, in (
                db.query(AgentAction.action_id)
                .filter(
                    AgentAction.session_id == session_id,
                    AgentAction.employee_id == employee_id,
                    AgentAction.status == "待确认",
                )
                .all()
            )
        ]
    finally:
        db.close()
    for action_id in action_ids:
        try:
            pending_store.cancel(action_id, employee_id)
        except (KeyError, ValueError):
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Agent task-level eval")
    parser.add_argument("--limit", type=int, default=0, help="只执行前 N 条")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="只校验评测数据，不调用模型",
    )
    args = parser.parse_args()

    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    if args.limit > 0:
        questions = questions[: args.limit]
    errors: list[str] = []
    ids = [str(item.get("id", "")) for item in questions]
    if len(ids) != len(set(ids)):
        errors.append("评测 ID 存在重复")
    for item in questions:
        if not item.get("employee_id") or not item.get("role"):
            errors.append(f"{item.get('id')} 缺少员工或角色")
        if not item.get("prompt") and not item.get("turns"):
            errors.append(f"{item.get('id')} 缺少 prompt 或 turns")
        if not isinstance(item.get("required_tools", []), list):
            errors.append(f"{item.get('id')} 的 required_tools 不是列表")
    if errors:
        raise SystemExit("评测数据校验失败：\n" + "\n".join(errors))

    if args.validate_only:
        categories = {
            category: sum(
                1
                for item in questions
                if item.get("category", "基础任务") == category
            )
            for category in sorted(
                {
                    item.get("category", "基础任务")
                    for item in questions
                }
            )
        }
        validation = {
            "validated_at": datetime.now().isoformat(timespec="seconds"),
            "total": len(questions),
            "unique_ids": len(set(ids)),
            "categories": categories,
        }
        VALIDATION_PATH.write_text(
            json.dumps(validation, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(
            f"评测数据校验通过：{validation['total']} 条，"
            f"{validation['unique_ids']} 个唯一 ID"
        )
        print(f"结果：{VALIDATION_PATH}")
        return

    if not DEEPSEEK_API_KEY:
        print("未配置 DEEPSEEK_API_KEY，无法执行 Agent 评测")
        return
    init_db()
    db = SessionLocal()
    try:
        reset_interview_data(db)
    finally:
        db.close()

    rows: list[dict] = []
    stop_reason = ""
    for question in questions:
        started = time.perf_counter()
        try:
            turns = question.get("turns") or [
                {"prompt": question["prompt"]}
            ]
            session_id = None
            result = None
            tools_used = []
            answers = []
            for turn in turns:
                result = run_agent(
                    message=turn["prompt"],
                    employee_id=turn.get(
                        "employee_id", question["employee_id"]
                    ),
                    role=turn.get("role", question["role"]),
                    session_id=session_id,
                )
                session_id = result.session_id
                tools_used.extend(result.tools_used)
                answers.append(result.answer)
            pending = _pending_exists(
                session_id, question["employee_id"]
            )
            answer = "\n".join(answers)
            error = ""
        except Exception as exc:
            tools_used = []
            pending = False
            answer = ""
            error = f"{type(exc).__name__}: {exc}"
            result = None
            if "Insufficient Balance" in error or "Error code: 402" in error:
                stop_reason = error
                break

        answer_contains = question.get("answer_contains", [])
        answer_any = question.get("answer_any", [])
        required_any_tools = question.get("required_any_tools", [])
        required_ok = bool(result) and all(
            tool in tools_used for tool in question["required_tools"]
        ) and (
            not required_any_tools
            or any(tool in tools_used for tool in required_any_tools)
        )
        forbidden_ok = all(
            tool not in tools_used
            for tool in question.get("forbidden_tools", [])
        )
        pending_ok = pending == question["expect_pending"]
        answer_ok = all(
            expected in answer for expected in answer_contains
        ) and (
            not answer_any
            or any(expected in answer for expected in answer_any)
        )
        passed = (
            required_ok
            and forbidden_ok
            and pending_ok
            and answer_ok
            and not error
        )
        prompt = " → ".join(turn["prompt"] for turn in turns)
        rows.append(
            {
                "id": question["id"],
                "category": question.get("category", "基础任务"),
                "prompt": prompt,
                "turn_count": len(turns),
                "employee_id": question["employee_id"],
                "role": question["role"],
                "tools_used": tools_used,
                "required_ok": required_ok,
                "forbidden_ok": forbidden_ok,
                "pending_ok": pending_ok,
                "answer_ok": answer_ok,
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
        _clear_pending(session_id, question["employee_id"])
        print(
            f"{question['id']} {'PASS' if passed else 'FAIL'} | "
            f"tools={','.join(tools_used) or '-'}"
        )
        time.sleep(0.2)

    passed = sum(1 for row in rows if row["passed"])
    skipped = len(questions) - len(rows)
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(questions),
        "attempted": len(rows),
        "skipped": skipped,
        "passed": passed,
        "pass_rate": round(passed / len(rows), 4) if rows else 0.0,
        "complete": not stop_reason and skipped == 0,
        "stop_reason": stop_reason,
        "categories": {
            category: {
                "total": sum(
                    1 for row in rows if row["category"] == category
                ),
                "passed": sum(
                    1
                    for row in rows
                    if row["category"] == category and row["passed"]
                ),
            }
            for category in sorted({row["category"] for row in rows})
        },
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
        f"- 任务总数：{len(questions)}",
        f"- 已执行：{len(rows)}",
        f"- 未执行：{skipped}",
        f"- 通过数：{passed}",
        f"- 通过率：{summary['pass_rate'] * 100:.1f}%",
        f"- 完整执行：{'是' if summary['complete'] else '否'}",
        "",
        "| 编号 | 分类 | 结果 | 必需工具 | 越权检查 | 待确认检查 | 回答校验 | 耗时(ms) | 工具调用 |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| {id} | {category} | {result} | {required} | {forbidden} | "
            "{pending} | {answer_ok} | {elapsed} | {tools} |".format(
                id=row["id"],
                category=row["category"],
                result="PASS" if row["passed"] else "FAIL",
                required="PASS" if row["required_ok"] else "FAIL",
                forbidden="PASS" if row["forbidden_ok"] else "FAIL",
                pending="PASS" if row["pending_ok"] else "FAIL",
                answer_ok="PASS" if row["answer_ok"] else "FAIL",
                elapsed=row["elapsed_ms"],
                tools=", ".join(row["tools_used"]) or "-",
            )
        )
    lines.extend(["", "## 分类统计", ""])
    lines.append("| 分类 | 通过/总数 |")
    lines.append("| --- | ---: |")
    for category, counts in summary["categories"].items():
        lines.append(
            f"| {category} | {counts['passed']}/{counts['total']} |"
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
    if stop_reason:
        lines.extend(
            [
                "",
                "## 执行中断",
                "",
                "本次评测因模型服务余额不足提前终止。"
                "未执行用例不计入业务失败，充值后重新运行即可生成完整报告。",
                "",
                f"原始错误：`{stop_reason}`",
            ]
        )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if skipped:
        print(
            f"\nAgent 评测：{passed}/{len(rows)} 通过，"
            f"{skipped} 条未执行"
        )
    else:
        print(f"\nAgent 评测：{passed}/{len(rows)} 通过")
    print(f"结果：{RESULTS_PATH}")
    print(f"报告：{REPORT_PATH}")


if __name__ == "__main__":
    main()
