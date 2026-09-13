from app.database import SessionLocal
from app.interview_data_import import import_interview_data
from app.models import (
    AgentAction,
    AppSetting,
    Employee,
    LeaveBalance,
    LeaveRequest,
)


def test_import_interview_dataset_is_complete_and_idempotent():
    db = SessionLocal()
    try:
        db.query(AgentAction).delete()
        db.query(LeaveRequest).delete()
        db.query(LeaveBalance).delete()
        db.query(Employee).delete()
        db.query(AppSetting).delete()
        db.commit()

        first = import_interview_data(db)
        assert first == {
            "employees": 20,
            "balances": 20,
            "leave_requests": 7,
        }
        employee = (
            db.query(Employee)
            .filter(Employee.employee_id == "E001")
            .first()
        )
        assert employee.manager_id == "M001"
        assert employee.department_head_id == "M001"
        request = (
            db.query(LeaveRequest)
            .filter(LeaveRequest.request_id == "LR-2026-0901")
            .first()
        )
        assert request.status == "待审批"
        assert request.approver_id == "M001"

        second = import_interview_data(db)
        assert second == first
        assert db.query(Employee).count() == 20
        assert db.query(LeaveBalance).count() == 20
        assert db.query(LeaveRequest).count() == 7
    finally:
        db.close()
