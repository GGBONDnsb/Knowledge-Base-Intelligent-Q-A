from __future__ import annotations

from sqlalchemy.orm import Session

from app.interview_data_import import DATA_VERSION, import_interview_data
from app.models import AppSetting

DEMO_YEAR = 2026


def ensure_demo_data(db: Session) -> bool:
    """Import the versioned interview dataset once, then preserve user changes."""
    marker = db.get(AppSetting, DATA_VERSION)
    if marker is not None:
        return False
    import_interview_data(db)
    return True
