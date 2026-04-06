from datetime import date, datetime

import pytest

from app.db.repository import RepositoryError, StudyRepository
from app.schemas.planner import DailyPlanItem, ProgressUpdateRequest, StudyPlanResponse, TopicGraphResponse, TopicNode


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

    def upsert(self, rows):
        self.inserted_rows = rows
        return _FakeExecute(self)


class _FakeSupabase:
    def __init__(self):
        self.tables = {}

    def table(self, name):
        if name not in self.tables:
            self.tables[name] = _FakeTable(name)
        return self.tables[name]


class _FailingExecute:
    def eq(self, _field, _value):
        return self

    def execute(self):
        raise RuntimeError("db write failed")


class _FailingTable:
    def delete(self):
        return _FailingExecute()

    def insert(self, _rows):
        return _FailingExecute()

    def upsert(self, _rows):
        return _FailingExecute()


class _FailingSupabase:
    def table(self, _name):
        return _FailingTable()


class _FakeReadResponse:
    def __init__(self, data):
        self.data = data


class _FakeReadTable:
    def __init__(self, rows):
        self.rows = rows

    def select(self, _fields):
        return self

    def eq(self, _field, _value):
        return self

    def order(self, _field):
        return self

    def execute(self):
        return _FakeReadResponse(self.rows)


class _FakeReadSupabase:
    def __init__(self, topic_rows, edge_rows):
        self.topic_rows = topic_rows
        self.edge_rows = edge_rows

    def table(self, name):
        if name == "topics":
            return _FakeReadTable(self.topic_rows)
        if name == "topic_edges":
            return _FakeReadTable(self.edge_rows)
        raise AssertionError(f"Unexpected table: {name}")


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


def test_graph_storage_is_scoped_by_user_and_course():
    repository = StudyRepository(None)
    graph = TopicGraphResponse(
        course_id="shared-course",
        topics=[TopicNode(id="t1", title="Foundations")],
        edges=[],
    )

    repository.save_topic_graph("u1", "shared-course", graph)

    assert repository.get_graph("u1", "shared-course") is not None
    assert repository.get_graph("u2", "shared-course") is None


def test_get_graph_rebuilds_relationships_from_edge_rows():
    repository = StudyRepository(
        _FakeReadSupabase(
            topic_rows=[
                {
                    "topic_id": "t1",
                    "title": "Foundations",
                    "description": "",
                    "difficulty": 2,
                    "estimated_minutes": 60,
                },
                {
                    "topic_id": "t2",
                    "title": "Algorithms",
                    "description": "",
                    "difficulty": 3,
                    "estimated_minutes": 90,
                },
            ],
            edge_rows=[
                {"source": "t1", "target": "t2", "edge_type": "dependency", "weight": 1.0},
                {"source": "t1", "target": "t2", "edge_type": "similarity", "weight": 0.9},
            ],
        )
    )

    graph = repository.get_graph("u1", "c1")

    assert graph is not None
    topic_by_id = {topic.id: topic for topic in graph.topics}
    assert topic_by_id["t2"].dependencies == ["t1"]
    assert topic_by_id["t1"].similarity_links == ["t2"]
    assert topic_by_id["t2"].similarity_links == ["t1"]


def test_save_plan_does_not_cache_state_when_database_write_fails():
    repository = StudyRepository(_FailingSupabase())
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

    with pytest.raises(RepositoryError):
        repository.save_plan(plan)

    assert ("u1", "c1") not in repository._memory_plans


def test_save_progress_does_not_cache_state_when_database_write_fails():
    repository = StudyRepository(_FailingSupabase())
    update = ProgressUpdateRequest(
        user_id="u1",
        course_id="c1",
        topic_id="t1",
        date=date(2026, 3, 1),
        minutes_spent=45,
        completed=False,
    )

    with pytest.raises(RepositoryError):
        repository.save_progress(update)

    assert repository._memory_progress[("u1", "c1")] == []
