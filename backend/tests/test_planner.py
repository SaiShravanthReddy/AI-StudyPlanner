from datetime import date

from app.core.config import Settings
from app.schemas.planner import TopicNode
from app.services.planner_service import PlannerService


def _sample_topics() -> list[TopicNode]:
    return [
        TopicNode(id="t1", title="Foundations", difficulty=2, estimated_minutes=60, dependencies=[]),
        TopicNode(id="t2", title="Algorithms", difficulty=4, estimated_minutes=90, dependencies=["t1"]),
        TopicNode(id="t3", title="Optimization", difficulty=5, estimated_minutes=90, dependencies=["t2"]),
    ]


def test_planner_respects_dependencies():
    planner = PlannerService(Settings())
    plan = planner.generate_plan(
        user_id="u1",
        course_id="c1",
        topics=_sample_topics(),
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 4),
        daily_study_minutes=120,
    )
    first_index = {item.topic_id: idx for idx, item in enumerate(plan.items)}
    assert first_index["t1"] < first_index["t2"] < first_index["t3"]


def test_replan_excludes_completed_topics():
    planner = PlannerService(Settings())
    plan = planner.generate_plan(
        user_id="u1",
        course_id="c1",
        topics=_sample_topics(),
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 4),
        daily_study_minutes=120,
        completed_topic_ids={"t1"},
    )
    topic_ids = {item.topic_id for item in plan.items}
    assert "t1" not in topic_ids
    assert {"t2", "t3"}.issubset(topic_ids)

