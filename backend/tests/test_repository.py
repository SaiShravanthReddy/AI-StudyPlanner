from datetime import date, datetime

from app.db.repository import StudyRepository
from app.schemas.planner import DailyPlanItem, StudyPlanResponse


class _FakeExecute:
    def __init__(self, table):
        self.table = table

    def eq(self, field, value):
        self.table.filters.append((field, value))
        return self

    def execute(self):
        return self


class _FakeTable:
    def __init__(self, name):
        self.name = name
        self.filters = []
        self.deleted = False
        self.inserted_rows = None

    def delete(self):
        self.deleted = True
        return _FakeExecute(self)

    def insert(self, rows):
        self.inserted_rows = rows
        return _FakeExecute(self)


class _FakeSupabase:
    def __init__(self):
        self.tables = {}

    def table(self, name):
        if name not in self.tables:
            self.tables[name] = _FakeTable(name)
        return self.tables[name]


def _build_plan(items):
    return StudyPlanResponse(
        user_id="u1",
        course_id="c1",
        generated_at=datetime(2026, 3, 1, 9, 0, 0),
        items=items,
    )


def test_save_plan_replaces_existing_rows_before_insert():
    supabase = _FakeSupabase()
    repository = StudyRepository(supabase)
    plan = _build_plan(
        [
            DailyPlanItem(
                date=date(2026, 3, 1),
                topic_id="t1",
                topic_title="Foundations",
                planned_minutes=60,
                status="completed",
                rationale="Finish prerequisites.",
            )
        ]
    )

    repository.save_plan(plan)

    plan_table = supabase.tables["study_plan_items"]
    assert plan_table.deleted is True
    assert plan_table.filters == [("user_id", "u1"), ("course_id", "c1")]
    assert plan_table.inserted_rows == [
        {
            "user_id": "u1",
            "course_id": "c1",
            "date": "2026-03-01",
            "topic_id": "t1",
            "topic_title": "Foundations",
            "planned_minutes": 60,
            "status": "completed",
            "rationale": "Finish prerequisites.",
        }
    ]


def test_save_plan_deletes_stale_rows_when_replan_is_empty():
    supabase = _FakeSupabase()
    repository = StudyRepository(supabase)
    plan = _build_plan([])

    repository.save_plan(plan)

    plan_table = supabase.tables["study_plan_items"]
    assert plan_table.deleted is True
    assert plan_table.filters == [("user_id", "u1"), ("course_id", "c1")]
    assert plan_table.inserted_rows is None
