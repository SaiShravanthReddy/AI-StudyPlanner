from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from app.core.config import Settings
from app.schemas.planner import RoadmapItem, RoadmapResponse, TopicNode

_DIFFICULTY_LABEL = {1: "Low", 2: "Low", 3: "Medium", 4: "High", 5: "High"}
_DAILY_BUDGET = {"easy": 60, "medium": 120, "hard": 180}
_TIME_MULTIPLIER = {"easy": 0.75, "medium": 1.0, "hard": 1.5}


def _priority_label(num_deps: int) -> str:
    if num_deps == 0:
        return "High"
    if num_deps == 1:
        return "Medium"
    return "Low"


class PlannerService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate_roadmap(
        self,
        course_id: str,
        topics: list[TopicNode],
        start_date: date,
        end_date: Optional[date],
        difficulty_level: str,
    ) -> RoadmapResponse:
        end_date = end_date or (start_date + timedelta(days=self.settings.default_planning_window_days - 1))

        if not topics:
            return RoadmapResponse(course_id=course_id, generated_at=datetime.utcnow(), items=[])

        daily_budget = _DAILY_BUDGET.get(difficulty_level, 120)
        multiplier = _TIME_MULTIPLIER.get(difficulty_level, 1.0)
        topic_by_id = {t.id: t for t in topics}
        ordered = self._toposort(topics, topic_by_id)

        current_date = start_date
        day_budget = daily_budget
        items: list[RoadmapItem] = []

        for topic in ordered:
            suggested = max(15, int(topic.estimated_minutes * multiplier))

            if day_budget < 15 and current_date < end_date:
                current_date += timedelta(days=1)
                day_budget = daily_budget

            dep_title: Optional[str] = None
            if topic.dependencies:
                first_dep = topic.dependencies[0]
                if first_dep in topic_by_id:
                    dep_title = topic_by_id[first_dep].title

            items.append(RoadmapItem(
                id=topic.id,
                topic=topic.title,
                date=current_date,
                suggested_minutes=suggested,
                difficulty=_DIFFICULTY_LABEL[topic.difficulty],
                priority=_priority_label(len(topic.dependencies)),
                dependency=dep_title,
                completed=False,
            ))

            day_budget -= suggested
            while day_budget < 0 and current_date < end_date:
                current_date += timedelta(days=1)
                day_budget += daily_budget

        return RoadmapResponse(
            course_id=course_id,
            generated_at=datetime.utcnow(),
            items=items,
        )

    def _toposort(self, topics: list[TopicNode], topic_by_id: dict) -> list[TopicNode]:
        indegree: dict[str, int] = {t.id: 0 for t in topics}
        outgoing: dict[str, list[str]] = defaultdict(list)
        for t in topics:
            for dep in t.dependencies:
                if dep in topic_by_id:
                    indegree[t.id] += 1
                    outgoing[dep].append(t.id)

        queue: list[tuple] = []
        for t in topics:
            if indegree[t.id] == 0:
                heapq.heappush(queue, self._sort_key(t))

        ordered: list[TopicNode] = []
        remaining = set(topic_by_id.keys())

        while remaining:
            if not queue:
                # break cycles by picking hardest remaining topic
                best = sorted(
                    (topic_by_id[tid] for tid in remaining),
                    key=self._sort_key,
                )[0]
                heapq.heappush(queue, self._sort_key(best))

            _, _, tid = heapq.heappop(queue)
            if tid not in remaining:
                continue

            ordered.append(topic_by_id[tid])
            remaining.remove(tid)

            for nxt in outgoing[tid]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0 and nxt in remaining:
                    heapq.heappush(queue, self._sort_key(topic_by_id[nxt]))

        return ordered

    def _sort_key(self, topic: TopicNode) -> tuple:
        return (topic.difficulty, topic.estimated_minutes, topic.id)
