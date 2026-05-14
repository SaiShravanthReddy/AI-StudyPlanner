from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional, Set

from app.core.config import Settings
from app.schemas.planner import DailyPlanItem, StudyPlanResponse, TopicNode


@dataclass
class _TopicWorkItem:
    topic: TopicNode
    remaining_minutes: int


class PlannerService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate_plan(
        self,
        course_id: str,
        topics: list[TopicNode],
        start_date: date,
        end_date: Optional[date],
        daily_study_minutes: int,
        completed_topic_ids: Optional[Set[str]] = None,
    ) -> StudyPlanResponse:
        completed_topic_ids = completed_topic_ids or set()
        end_date = end_date or (start_date + timedelta(days=self.settings.default_planning_window_days - 1))
        active_topics = [topic for topic in topics if topic.id not in completed_topic_ids]
        if not active_topics:
            return StudyPlanResponse(course_id=course_id, generated_at=datetime.utcnow(), items=[])

        topic_by_id = {topic.id: topic for topic in active_topics}
        indegree: dict[str, int] = {topic.id: 0 for topic in active_topics}
        outgoing = defaultdict(list)
        for topic in active_topics:
            for dep in topic.dependencies:
                if dep not in topic_by_id:
                    continue
                indegree[topic.id] += 1
                outgoing[dep].append(topic.id)

        work_state = {
            topic.id: _TopicWorkItem(topic=topic, remaining_minutes=max(15, topic.estimated_minutes))
            for topic in active_topics
        }
        available: list[tuple[int, int, str]] = []
        for topic in active_topics:
            if indegree[topic.id] == 0:
                heapq.heappush(available, self._priority_tuple(topic))

        plan_items: list[DailyPlanItem] = []
        pending_ids = set(topic_by_id.keys())

        for day in self._daterange(start_date, end_date):
            if not pending_ids:
                break
            budget = daily_study_minutes
            while budget >= 15 and pending_ids:
                if not available:
                    next_id = self._unlock_cycle(work_state, pending_ids)
                    heapq.heappush(available, self._priority_tuple(work_state[next_id].topic))

                _, _, topic_id = heapq.heappop(available)
                if topic_id not in pending_ids:
                    continue

                block = work_state[topic_id]
                allocation = min(budget, block.remaining_minutes)
                budget -= allocation
                block.remaining_minutes -= allocation
                completed = block.remaining_minutes <= 0
                status = "completed" if completed else "in_progress"
                rationale = self._rationale(block.topic, completed)
                plan_items.append(
                    DailyPlanItem(
                        date=day,
                        topic_id=topic_id,
                        topic_title=block.topic.title,
                        planned_minutes=allocation,
                        status=status,
                        rationale=rationale,
                    )
                )
                if completed:
                    pending_ids.remove(topic_id)
                    for nxt in outgoing[topic_id]:
                        indegree[nxt] -= 1
                        if indegree[nxt] == 0 and nxt in pending_ids:
                            heapq.heappush(available, self._priority_tuple(work_state[nxt].topic))
                else:
                    heapq.heappush(available, self._priority_tuple(block.topic))
                if budget < 15:
                    break
        return StudyPlanResponse(course_id=course_id, generated_at=datetime.utcnow(), items=plan_items)

    def _priority_tuple(self, topic: TopicNode) -> tuple[int, int, str]:
        return (-topic.difficulty, -topic.estimated_minutes, topic.id)

    def _unlock_cycle(self, work_state: dict[str, _TopicWorkItem], pending_ids: set[str]) -> str:
        # If extracted dependencies produce a cycle, unblock the hardest remaining topic.
        best = sorted(
            (work_state[topic_id].topic for topic_id in pending_ids),
            key=lambda topic: (-topic.difficulty, -topic.estimated_minutes, topic.id),
        )[0]
        return best.id

    def _daterange(self, start: date, end: date) -> list[date]:
        current = start
        days = []
        while current <= end:
            days.append(current)
            current += timedelta(days=1)
        return days

    def _rationale(self, topic: TopicNode, completed: bool) -> str:
        if completed:
            return f"Finished '{topic.title}' to unlock downstream topics."
        return f"Continue high-impact work on '{topic.title}' (difficulty {topic.difficulty}/5)."
