from datetime import date, datetime
from unittest.mock import patch

from app.core.config import Settings
from app.schemas.planner import DailyPlanItem, StudyPlanResponse
from app.services.reminder_service import ReminderService


def test_reminders_default_to_configured_timezone():
    service = ReminderService(Settings(timezone="America/New_York"))
    plan = StudyPlanResponse(
        user_id="u1",
        course_id="c1",
        generated_at=datetime(2026, 3, 1, 12, 0, 0),
        items=[
            DailyPlanItem(
                date=date(2026, 3, 2),
                topic_id="t1",
                topic_title="Foundations",
                planned_minutes=60,
                status="pending",
                rationale="Review basics.",
            )
        ],
    )

    fake_now = datetime(2026, 3, 1, 23, 30, 0)
    with patch("app.services.reminder_service.datetime") as mock_datetime:
        mock_datetime.now.return_value = fake_now
        reminders = service.build_daily_reminders(plan)

    assert reminders == ["2026-03-02: 60 min on Foundations (pending)"]
