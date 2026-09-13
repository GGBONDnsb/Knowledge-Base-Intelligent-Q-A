from __future__ import annotations

from sqlalchemy import text

from app.database import engine

ADD_COLUMNS: dict[str, dict[str, str]] = {
    "employees": {
        "manager_id": "VARCHAR DEFAULT ''",
        "department_head_id": "VARCHAR DEFAULT ''",
    },
    "leave_requests": {
        "approver_id": "VARCHAR DEFAULT ''",
        "submitted_at": "DATETIME",
        "approved_at": "DATETIME",
        "rejected_at": "DATETIME",
        "reject_reason": "TEXT DEFAULT ''",
        "cancelled_at": "DATETIME",
    },
}


def _table_columns(connection, table_name: str) -> set[str]:
    rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def apply_schema_updates() -> list[str]:
    if engine.dialect.name != "sqlite":
        return []

    changes: list[str] = []
    with engine.begin() as connection:
        for table_name, columns in ADD_COLUMNS.items():
            existing = _table_columns(connection, table_name)
            if not existing:
                continue
            for column_name, definition in columns.items():
                if column_name in existing:
                    continue
                connection.execute(
                    text(
                        f"ALTER TABLE {table_name} "
                        f"ADD COLUMN {column_name} {definition}"
                    )
                )
                changes.append(f"{table_name}.{column_name}")

        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "uq_leave_balance_employee_year_type "
                "ON leave_balances(employee_id, year, leave_type)"
            )
        )
    return changes
