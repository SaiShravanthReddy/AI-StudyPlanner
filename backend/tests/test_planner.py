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


def test_roadmap_respects_dependencies():
    planner = PlannerService(Settings())
    roadmap = planner.generate_roadmap(
        course_id="c1",
        topics=_sample_topics(),
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 10),
        difficulty_level="medium",
    )
    order = {item.id: idx for idx, item in enumerate(roadmap.items)}
    assert order["t1"] < order["t2"] < order["t3"]


def test_roadmap_assigns_correct_priority():
    planner = PlannerService(Settings())
    roadmap = planner.generate_roadmap(
        course_id="c1",
        topics=_sample_topics(),
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 10),
        difficulty_level="medium",
    )
    by_id = {item.id: item for item in roadmap.items}
    # t1 unlocks t2 and t3 transitively → High
    # t2 unlocks t3 directly → Medium
    # t3 unlocks nothing → Low
    assert by_id["t1"].priority == "High"
    assert by_id["t2"].priority == "Medium"
    assert by_id["t3"].priority == "Low"


def test_roadmap_scales_time_with_difficulty():
    planner = PlannerService(Settings())
    easy = planner.generate_roadmap(
        course_id="c1",
        topics=_sample_topics(),
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 10),
        difficulty_level="easy",
    )
    hard = planner.generate_roadmap(
        course_id="c1",
        topics=_sample_topics(),
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 10),
        difficulty_level="hard",
    )
    assert sum(i.suggested_minutes for i in hard.items) > sum(i.suggested_minutes for i in easy.items)
