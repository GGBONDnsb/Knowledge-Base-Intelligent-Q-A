from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models import (
    ActionEvent,
    AgentAction,
    AppSetting,
    Employee,
    LeaveBalance,
    LeaveRequest,
)

DATA_VERSION = "interview_data_v1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = Path(
    os.environ.get("INTERVIEW_DATA_DIR", PROJECT_ROOT / "interview_data")
)
ALLOWED_REQUEST_STATUSES = {"待审批", "已批准", "已拒绝", "已取消"}
ALLOWED_EMPLOYEE_ROLES = {"employee", "manager", "admin"}


def _load_json(data_dir: Path, filename: str) -> Any:
    path = data_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"缺少数据文件：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_date(value: str, field: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 日期格式错误：{value}") from exc


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).replace(tzinfo=None)


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicated: set[str] = set()
    for value in values:
        if value in seen:
            duplicated.add(value)
        seen.add(value)
    return sorted(duplicated)


def validate_dataset(
    employees: list[dict],
    balances: list[dict],
    requests: list[dict],
) -> list[str]:
    errors: list[str] = []
    employee_ids = [str(item.get("employee_id", "")) for item in employees]
    duplicated_employees = _duplicates(employee_ids)
    if duplicated_employees:
        errors.append(f"员工编号重复：{', '.join(duplicated_employees)}")

    employee_by_id = {str(item["employee_id"]): item for item in employees}
    manager_ids = {
        str(item["employee_id"])
        for item in employees
        if item.get("role") == "manager"
    }

    for employee in employees:
        employee_id = str(employee.get("employee_id", ""))
        role = employee.get("role")
        if role not in ALLOWED_EMPLOYEE_ROLES:
            errors.append(f"{employee_id} 的 role 非法：{role}")
        manager_id = employee.get("manager_id")
        department_head_id = employee.get("department_head_id")
        if manager_id and manager_id not in manager_ids:
            errors.append(f"{employee_id} 的直属主管不存在：{manager_id}")
        if department_head_id and department_head_id not in manager_ids:
            errors.append(
                f"{employee_id} 的部门负责人不存在：{department_head_id}"
            )
        if manager_id and role == "employee":
            manager = employee_by_id.get(manager_id, {})
            if manager.get("department") != employee.get("department"):
                errors.append(f"{employee_id} 与直属主管不属于同一部门")
        if department_head_id and role == "employee":
            department_head = employee_by_id.get(department_head_id, {})
            if department_head.get("department") != employee.get("department"):
                errors.append(f"{employee_id} 与部门负责人不属于同一部门")

    for employee_id in employee_ids:
        visited: set[str] = set()
        current = employee_id
        while current:
            if current in visited:
                errors.append(f"员工主管关系存在循环：{employee_id}")
                break
            visited.add(current)
            current = str(
                employee_by_id.get(current, {}).get("manager_id") or ""
            )

    balance_keys = [
        (
            str(item.get("employee_id", "")),
            int(item.get("year", 0)),
            str(item.get("leave_type", "")),
        )
        for item in balances
    ]
    duplicated_balances = [
        key for key in set(balance_keys) if balance_keys.count(key) > 1
    ]
    if duplicated_balances:
        errors.append(f"余额记录重复：{duplicated_balances}")

    for balance in balances:
        employee_id = str(balance.get("employee_id", ""))
        if employee_id not in employee_by_id:
            errors.append(f"余额记录引用了不存在的员工：{employee_id}")
            continue
        total_days = float(balance.get("total_days", 0))
        used_days = float(balance.get("used_days", 0))
        remaining_days = float(balance.get("remaining_days", 0))
        if total_days < 0 or used_days < 0:
            errors.append(f"{employee_id} 的年假余额不能为负数")
        if used_days > total_days:
            errors.append(f"{employee_id} 的已用年假超过总额")
        if abs((total_days - used_days) - remaining_days) > 1e-6:
            errors.append(f"{employee_id} 的剩余年假计算不一致")

    request_ids = [str(item.get("request_id", "")) for item in requests]
    duplicated_requests = _duplicates(request_ids)
    if duplicated_requests:
        errors.append(f"申请编号重复：{', '.join(duplicated_requests)}")

    for request in requests:
        request_id = str(request.get("request_id", ""))
        employee_id = str(request.get("employee_id", ""))
        approver_id = str(request.get("approver_id", ""))
        employee = employee_by_id.get(employee_id)
        if employee is None:
            errors.append(f"{request_id} 的申请人不存在：{employee_id}")
            continue
        if approver_id not in manager_ids:
            errors.append(f"{request_id} 的审批人不存在：{approver_id}")
        status = request.get("status")
        if status not in ALLOWED_REQUEST_STATUSES:
            errors.append(f"{request_id} 的状态非法：{status}")
        try:
            start = _parse_date(
                str(request.get("start_date", "")), "start_date"
            )
            end = _parse_date(str(request.get("end_date", "")), "end_date"
            )
        except ValueError as exc:
            errors.append(f"{request_id}: {exc}")
            continue
        if end < start:
            errors.append(f"{request_id} 的结束日期早于开始日期")
        days = float(request.get("days", 0))
        if days <= 0 or abs(days * 2 - round(days * 2)) > 1e-6:
            errors.append(f"{request_id} 的天数不是 0.5 的整数倍")
        expected_approver = (
            str(employee.get("manager_id") or "")
            if days <= 3
            else str(employee.get("department_head_id") or "")
        )
        if approver_id != expected_approver:
            errors.append(
                f"{request_id} 的审批人应为 {expected_approver}，"
                f"实际为 {approver_id}"
            )
        if status == "已批准" and not request.get("approved_at"):
            errors.append(f"{request_id} 缺少 approved_at")
        if status == "已拒绝" and not request.get("rejected_at"):
            errors.append(f"{request_id} 缺少 rejected_at")
        if status == "已取消" and not request.get("cancelled_at"):
            errors.append(f"{request_id} 缺少 cancelled_at")

    return errors


def import_interview_data(
    db: Session,
    data_dir: Path | None = None,
) -> dict[str, int]:
    source_dir = data_dir or DEFAULT_DATA_DIR
    employees = _load_json(source_dir, "employees.json")
    balances = _load_json(source_dir, "leave_balances.json")
    requests = _load_json(source_dir, "leave_requests.json")

    errors = validate_dataset(employees, balances, requests)
    if errors:
        raise ValueError("模拟数据校验失败：\n" + "\n".join(errors))

    employee_map: dict[str, Employee] = {}
    for item in employees:
        employee_id = str(item["employee_id"])
        employee = (
            db.query(Employee)
            .filter(Employee.employee_id == employee_id)
            .first()
        )
        if employee is None:
            employee = Employee(employee_id=employee_id)
            db.add(employee)
        employee.name = str(item.get("name", ""))
        employee.department = str(item.get("department", ""))
        employee.position = str(item.get("position", ""))
        employee.work_years = int(item.get("work_years", 0))
        employee.role = str(item.get("role", "employee"))
        employee.manager_id = str(item.get("manager_id") or "")
        employee.department_head_id = str(item.get("department_head_id") or "")
        db.flush()
        employee_map[employee_id] = employee

    for item in balances:
        employee = employee_map[str(item["employee_id"])]
        balance = (
            db.query(LeaveBalance)
            .filter(
                LeaveBalance.employee_id == employee.id,
                LeaveBalance.year == int(item["year"]),
                LeaveBalance.leave_type == str(item["leave_type"]),
            )
            .first()
        )
        if balance is None:
            balance = LeaveBalance(
                employee_id=employee.id,
                year=int(item["year"]),
                leave_type=str(item["leave_type"]),
            )
            db.add(balance)
        balance.total_days = float(item["total_days"])
        balance.used_days = float(item["used_days"])

    for item in requests:
        employee = employee_map[str(item["employee_id"])]
        request_id = str(item["request_id"])
        request = (
            db.query(LeaveRequest)
            .filter(LeaveRequest.request_id == request_id)
            .first()
        )
        if request is None:
            request = LeaveRequest(request_id=request_id)
            db.add(request)
        request.employee_id = employee.id
        request.leave_type = str(item["leave_type"])
        request.start_date = str(item["start_date"])
        request.end_date = str(item["end_date"])
        request.days = float(item["days"])
        request.reason = str(item.get("reason", ""))
        request.status = str(item["status"])
        request.approver_id = str(item["approver_id"])
        request.submitted_at = _parse_datetime(item.get("submitted_at"))
        request.approved_at = _parse_datetime(item.get("approved_at"))
        request.rejected_at = _parse_datetime(item.get("rejected_at"))
        request.reject_reason = str(item.get("reject_reason", ""))
        request.cancelled_at = _parse_datetime(item.get("cancelled_at"))
        if request.created_at is None:
            request.created_at = request.submitted_at

    marker = db.get(AppSetting, DATA_VERSION)
    if marker is None:
        marker = AppSetting(key=DATA_VERSION)
        db.add(marker)
    marker.value = datetime.now().date().isoformat()
    db.commit()

    return {
        "employees": len(employees),
        "balances": len(balances),
        "leave_requests": len(requests),
    }


def reset_interview_data(
    db: Session,
    data_dir: Path | None = None,
) -> dict[str, int]:
    db.query(ActionEvent).delete()
    db.query(AgentAction).delete()
    db.query(LeaveRequest).delete()
    db.query(LeaveBalance).delete()
    db.commit()
    return import_interview_data(db, data_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="导入员工服务 Agent 模拟数据")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="模拟数据目录",
    )
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        result = import_interview_data(db, args.data_dir)
    finally:
        db.close()
    print(
        "导入完成："
        f"{result['employees']} 名员工，"
        f"{result['balances']} 条余额，"
        f"{result['leave_requests']} 条请假申请"
    )


if __name__ == "__main__":
    main()
