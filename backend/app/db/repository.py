from __future__ import annotations

import logging
from collections import defaultdict
from copy import deepcopy
from typing import Any, Optional, TYPE_CHECKING

from app.schemas.planner import (
    ProgressUpdateRequest,
    RoadmapResponse,
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
        self._memory_roadmaps: dict[tuple[str, str], RoadmapResponse] = {}
        self._memory_completed: dict[tuple[str, str], set] = defaultdict(set)

    def save_course(self, course_payload: dict) -> None:
        user_id = str(course_payload["user_id"])
        course_id = str(course_payload["course_id"])
        if self.supabase:
            try:
                self.supabase.table("courses").upsert(course_payload).execute()
            except Exception as exc:
                logger.exception("Failed to persist course", extra={"user_id": user_id, "course_id": course_id})
                raise RepositoryError("Failed to persist course.") from exc
        self._memory_courses[(user_id, course_id)] = deepcopy(course_payload)

    def save_topic_graph(self, user_id: str, course_id: str, graph: TopicGraphResponse) -> None:
        if not self.supabase:
            self._memory_graphs[(user_id, course_id)] = deepcopy(graph)
            return
        topic_rows = []
        for topic in graph.topics:
            topic_rows.append({
                "user_id": user_id,
                "course_id": course_id,
                "topic_id": topic.id,
                "title": topic.title,
                "description": topic.description,
                "difficulty": topic.difficulty,
                "estimated_minutes": topic.estimated_minutes,
            })
        edge_rows = []
        for edge in graph.edges:
            edge_rows.append({
                "user_id": user_id,
                "course_id": course_id,
                "source": edge.source,
                "target": edge.target,
                "edge_type": edge.edge_type,
                "weight": edge.weight,
            })
        try:
            self.supabase.table("topics").upsert(topic_rows).execute()
            self.supabase.table("topic_edges").upsert(edge_rows).execute()
        except Exception as exc:
            logger.exception("Failed to persist topic graph", extra={"user_id": user_id, "course_id": course_id})
            raise RepositoryError("Failed to persist topic graph.") from exc
        self._memory_graphs[(user_id, course_id)] = deepcopy(graph)

    def save_roadmap(self, user_id: str, roadmap: RoadmapResponse) -> None:
        if not self.supabase:
            self._memory_roadmaps[(user_id, roadmap.course_id)] = deepcopy(roadmap)
            return
        rows = []
        for item in roadmap.items:
            rows.append({
                "user_id": user_id,
                "course_id": roadmap.course_id,
                "topic_id": item.id,
                "topic": item.topic,
                "date": item.date.isoformat(),
                "suggested_minutes": item.suggested_minutes,
                "difficulty": item.difficulty,
                "priority": item.priority,
                "dependency": item.dependency,
            })
        try:
            table = self.supabase.table("study_plan_items")
            table.delete().eq("user_id", user_id).eq("course_id", roadmap.course_id).execute()
            if rows:
                table.insert(rows).execute()
        except Exception as exc:
            logger.exception("Failed to persist roadmap", extra={"user_id": user_id, "course_id": roadmap.course_id})
            raise RepositoryError("Failed to persist roadmap.") from exc
        self._memory_roadmaps[(user_id, roadmap.course_id)] = deepcopy(roadmap)

    def get_roadmap(self, user_id: str, course_id: str) -> Optional[RoadmapResponse]:
        return deepcopy(self._memory_roadmaps.get((user_id, course_id)))

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
                .data or []
            )
            edge_rows = (
                self.supabase.table("topic_edges")
                .select("*")
                .eq("user_id", user_id)
                .eq("course_id", course_id)
                .execute()
                .data or []
            )
            if not topic_rows:
                return None
            dependency_map: dict = defaultdict(list)
            similarity_map: dict = defaultdict(list)
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

    def save_progress(self, user_id: str, update: ProgressUpdateRequest) -> None:
        key = (user_id, update.course_id)
        if update.completed:
            self._memory_completed[key].add(update.topic_id)
        else:
            self._memory_completed[key].discard(update.topic_id)
        if not self.supabase:
            return
        try:
            self.supabase.table("progress_events").upsert(
                {"user_id": user_id, "course_id": update.course_id, "topic_id": update.topic_id, "completed": update.completed},
                on_conflict="user_id,course_id,topic_id",
            ).execute()
        except Exception as exc:
            logger.exception("Failed to persist progress", extra={"user_id": user_id, "course_id": update.course_id})
            raise RepositoryError("Failed to persist progress.") from exc

    def get_completed_topic_ids(self, user_id: str, course_id: str) -> set:
        return set(self._memory_completed.get((user_id, course_id), set()))
