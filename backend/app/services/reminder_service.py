from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from app.schemas.planner import StudyPlanResponse


class ReminderService:
    def build_daily_reminders(self, plan: StudyPlanResponse, for_day: Optional[date] = None) -> list[str]:
        if for_day is None:
            for_day = date.today() + timedelta(days=1)
        next_items = [item for item in plan.items if item.date == for_day]
        if not next_items:
            return [f"No study blocks planned for {for_day.isoformat()}. Consider adding review time."]
        reminders = []
        for item in next_items:
            reminders.append(
                f"{for_day.isoformat()}: {item.planned_minutes} min on {item.topic_title} ({item.status})"
            )
        return reminders
