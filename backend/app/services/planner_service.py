from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from app.core.config import Settings
from app.schemas.planner import RoadmapItem, RoadmapResponse, TopicNode

_DAILY_BUDGET = {"easy": 60, "medium": 120, "hard": 180}
_TIME_MULTIPLIER = {"easy": 0.75, "medium": 1.0, "hard": 1.5}


def _transitive_dependents(topics: list[TopicNode]) -> dict[str, int]:
    """Count how many topics transitively depend on each topic (full chain, not just direct)."""
    topic_ids = {t.id for t in topics}
    reverse: dict[str, list[str]] = defaultdict(list)
    for t in topics:
        for dep_id in t.dependencies:
            if dep_id in topic_ids:
                reverse[dep_id].append(t.id)

    counts: dict[str, int] = {}
    for t in topics:
        seen: set[str] = set()
        queue = list(reverse[t.id])
        while queue:
            curr = queue.pop()
            if curr in seen:
                continue
            seen.add(curr)
            queue.extend(reverse[curr])
        counts[t.id] = len(seen)
    return counts


def _percentile_labels(topic_ids: list[str], scores: dict[str, float]) -> dict[str, str]:
    """Assign Low/Medium/High by splitting topics into thirds by score rank."""
    if not topic_ids:
        return {}
    ordered = sorted(topic_ids, key=lambda tid: (scores[tid], tid))
    n = len(ordered)
    low_end = max(1, n // 3)
    high_start = n - max(1, n // 3)
    result: dict[str, str] = {}
    for i, tid in enumerate(ordered):
        if i < low_end:
            result[tid] = "Low"
        elif i >= high_start:
            result[tid] = "High"
        else:
            result[tid] = "Medium"
    return result


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

        topic_ids = [t.id for t in ordered]

        # difficulty: percentile-rank GPT's 1-5 score within this topic set,
        # using estimated_minutes as a tiebreaker for topics with equal scores
        difficulty_scores = {
            t.id: t.difficulty + t.estimated_minutes / 10000
            for t in topics
        }
        difficulty_labels = _percentile_labels(topic_ids, difficulty_scores)

        # priority: percentile-rank transitive dependents (full chain), with
        # topological position as tiebreaker so earlier foundational topics
        # rank higher when the dependency graph is sparse
        transitive = _transitive_dependents(topics)
        position_by_id = {tid: i for i, tid in enumerate(topic_ids)}
        priority_scores = {
            tid: transitive[tid] * len(topics) + (len(topics) - position_by_id[tid])
            for tid in topic_ids
        }
        priority_labels = _percentile_labels(topic_ids, priority_scores)

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
                difficulty=difficulty_labels[topic.id],
                priority=priority_labels[topic.id],
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
