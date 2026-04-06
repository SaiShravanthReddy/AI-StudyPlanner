from __future__ import annotations

import logging
from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime
from typing import Any, Optional, TYPE_CHECKING

from app.schemas.planner import (
    DailyPlanItem,
    ProgressUpdateRequest,
    StudyPlanResponse,
    TopicEdge,
    TopicGraphResponse,
    TopicNode,
)

if TYPE_CHECKING:
    from supabase import Client
else:
    Client = Any

logger = logging.getLogger(__name__)


class RepositoryError(RuntimeError):
    pass


class StudyRepository:
    def __init__(self, supabase_client: Optional[Client]):
        self.supabase = supabase_client
        self._memory_courses: dict[tuple[str, str], dict] = {}
        self._memory_graphs: dict[tuple[str, str], TopicGraphResponse] = {}
        self._memory_plans: dict[tuple[str, str], StudyPlanResponse] = {}
        self._memory_progress: dict[tuple[str, str], list[dict]] = defaultdict(list)

    def save_course(self, course_payload: dict) -> None:
        user_id = str(course_payload["user_id"])
        course_id = str(course_payload["course_id"])
        if self.supabase:
            try:
                self.supabase.table("courses").upsert(course_payload).execute()
            except Exception as exc:
                logger.exception("Failed to persist course", extra={"user_id": user_id, "course_id": course_id})
                raise RepositoryError("Failed to persist course.") from exc
        if not self.supabase:
            self._memory_courses[(user_id, course_id)] = deepcopy(course_payload)
            return
        self._memory_courses[(user_id, course_id)] = deepcopy(course_payload)

    def save_topic_graph(self, user_id: str, course_id: str, graph: TopicGraphResponse) -> None:
        if not self.supabase:
            self._memory_graphs[(user_id, course_id)] = deepcopy(graph)
            return
        topic_rows = []
        for topic in graph.topics:
            topic_rows.append(
                {
                    "user_id": user_id,
                    "course_id": course_id,
                    "topic_id": topic.id,
                    "title": topic.title,
                    "description": topic.description,
                    "difficulty": topic.difficulty,
                    "estimated_minutes": topic.estimated_minutes,
                }
            )
        edge_rows = []
        for edge in graph.edges:
            edge_rows.append(
                {
                    "user_id": user_id,
                    "course_id": course_id,
                    "source": edge.source,
                    "target": edge.target,
                    "edge_type": edge.edge_type,
                    "weight": edge.weight,
                }
            )
        try:
            self.supabase.table("topics").upsert(topic_rows).execute()
            self.supabase.table("topic_edges").upsert(edge_rows).execute()
        except Exception as exc:
            logger.exception("Failed to persist topic graph", extra={"user_id": user_id, "course_id": course_id})
            raise RepositoryError("Failed to persist topic graph.") from exc
        self._memory_graphs[(user_id, course_id)] = deepcopy(graph)

    def save_plan(self, plan: StudyPlanResponse) -> None:
        if not self.supabase:
            self._memory_plans[(plan.user_id, plan.course_id)] = deepcopy(plan)
            return
        rows = []
        for item in plan.items:
            rows.append(
                {
                    "user_id": plan.user_id,
                    "course_id": plan.course_id,
                    "date": item.date.isoformat(),
                    "topic_id": item.topic_id,
                    "topic_title": item.topic_title,
                    "planned_minutes": item.planned_minutes,
                    "status": item.status,
                    "rationale": item.rationale,
                }
            )
        try:
            plan_table = self.supabase.table("study_plan_items")
            plan_table.delete().eq("user_id", plan.user_id).eq("course_id", plan.course_id).execute()
            if rows:
                plan_table.insert(rows).execute()
        except Exception as exc:
            logger.exception("Failed to persist study plan", extra={"user_id": plan.user_id, "course_id": plan.course_id})
            raise RepositoryError("Failed to persist study plan.") from exc
        self._memory_plans[(plan.user_id, plan.course_id)] = deepcopy(plan)

    def get_plan(self, user_id: str, course_id: str) -> Optional[StudyPlanResponse]:
        plan = self._memory_plans.get((user_id, course_id))
        if plan:
            return deepcopy(plan)
        if not self.supabase:
            return None
        try:
            response = (
                self.supabase.table("study_plan_items")
                .select("*")
                .eq("user_id", user_id)
                .eq("course_id", course_id)
                .order("date")
                .execute()
            )
            rows = response.data or []
            if not rows:
                return None
            items = []
            for row in rows:
                items.append(
                    DailyPlanItem(
                        date=date.fromisoformat(row["date"]),
                        topic_id=str(row["topic_id"]),
                        topic_title=str(row["topic_title"]),
                        planned_minutes=int(row["planned_minutes"]),
                        status=str(row.get("status", "pending")),
                        rationale=str(row.get("rationale", "")),
                    )
                )
            plan = StudyPlanResponse(
                user_id=user_id,
                course_id=course_id,
                generated_at=datetime.utcnow(),
                items=items,
            )
            self._memory_plans[(user_id, course_id)] = plan
            return deepcopy(plan)
        except Exception as exc:
            logger.exception("Failed to load study plan", extra={"user_id": user_id, "course_id": course_id})
            raise RepositoryError("Failed to load study plan.") from exc

    def get_graph(self, user_id: str, course_id: str) -> Optional[TopicGraphResponse]:
        graph = self._memory_graphs.get((user_id, course_id))
        if graph:
            return deepcopy(graph)
        if not self.supabase:
            return None
        try:
            topic_rows = (
                self.supabase.table("topics")
                .select("*")
                .eq("user_id", user_id)
                .eq("course_id", course_id)
                .execute()
                .data
                or []
            )
            edge_rows = (
                self.supabase.table("topic_edges")
                .select("*")
                .eq("user_id", user_id)
                .eq("course_id", course_id)
                .execute()
                .data
                or []
            )
            if not topic_rows:
                return None
            dependency_map: dict[str, list[str]] = defaultdict(list)
            similarity_map: dict[str, list[str]] = defaultdict(list)
            for row in edge_rows:
                source = str(row["source"])
                target = str(row["target"])
                edge_type = str(row.get("edge_type", "dependency"))
                if edge_type == "dependency":
                    dependency_map[target].append(source)
                elif edge_type == "similarity":
                    similarity_map[source].append(target)
                    similarity_map[target].append(source)
            topics = [
                TopicNode(
                    id=str(row["topic_id"]),
                    title=str(row["title"]),
                    description=str(row.get("description", "")),
                    difficulty=int(row.get("difficulty", 3)),
                    estimated_minutes=int(row.get("estimated_minutes", 60)),
                    dependencies=sorted(set(dependency_map.get(str(row["topic_id"]), []))),
                    similarity_links=sorted(set(similarity_map.get(str(row["topic_id"]), []))),
                )
                for row in topic_rows
            ]
            edges = [
                TopicEdge(
                    source=str(row["source"]),
                    target=str(row["target"]),
                    edge_type=str(row.get("edge_type", "dependency")),
                    weight=float(row.get("weight", 0.0)),
                )
                for row in edge_rows
            ]
            graph = TopicGraphResponse(course_id=course_id, topics=topics, edges=edges)
            self._memory_graphs[(user_id, course_id)] = graph
            return deepcopy(graph)
        except Exception as exc:
            logger.exception("Failed to load topic graph", extra={"user_id": user_id, "course_id": course_id})
            raise RepositoryError("Failed to load topic graph.") from exc

    def save_progress(self, update: ProgressUpdateRequest) -> None:
        row = {
            "user_id": update.user_id,
            "course_id": update.course_id,
            "topic_id": update.topic_id,
            "date": update.date.isoformat(),
            "minutes_spent": update.minutes_spent,
            "completed": update.completed,
        }
        if not self.supabase:
            self._memory_progress[(update.user_id, update.course_id)].append(deepcopy(row))
            return
        try:
            self.supabase.table("progress_events").insert(row).execute()
        except Exception as exc:
            logger.exception("Failed to persist progress", extra={"user_id": update.user_id, "course_id": update.course_id})
            raise RepositoryError("Failed to persist progress.") from exc
        self._memory_progress[(update.user_id, update.course_id)].append(deepcopy(row))

    def get_completed_topic_ids(self, user_id: str, course_id: str) -> set[str]:
        rows = self._memory_progress.get((user_id, course_id), [])
        completed = {str(row["topic_id"]) for row in rows if row.get("completed")}
        if completed or not self.supabase:
            return completed
        try:
            response = (
                self.supabase.table("progress_events")
                .select("topic_id,completed")
                .eq("user_id", user_id)
                .eq("course_id", course_id)
                .eq("completed", True)
                .execute()
            )
            rows = response.data or []
            completed = {str(row["topic_id"]) for row in rows if row.get("completed")}
            return completed
        except Exception as exc:
            logger.exception("Failed to load completed topics", extra={"user_id": user_id, "course_id": course_id})
            raise RepositoryError("Failed to load completed topics.") from exc

    def get_progress_rows(self, user_id: str, course_id: str) -> list[dict]:
        rows = self._memory_progress.get((user_id, course_id), [])
        if rows:
            return deepcopy(rows)
        if not self.supabase:
            return []
        try:
            response = (
                self.supabase.table("progress_events")
                .select("*")
                .eq("user_id", user_id)
                .eq("course_id", course_id)
                .order("date")
                .execute()
            )
            rows = response.data or []
            self._memory_progress[(user_id, course_id)] = deepcopy(rows)
            return rows
        except Exception as exc:
            logger.exception("Failed to load progress rows", extra={"user_id": user_id, "course_id": course_id})
            raise RepositoryError("Failed to load progress rows.") from exc
