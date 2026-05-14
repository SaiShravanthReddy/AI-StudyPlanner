from __future__ import annotations

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.config import Settings, get_settings
from app.db.repository import RepositoryError, StudyRepository
from app.db.supabase_client import build_supabase_client
from app.schemas.planner import (
    IngestResponse,
    ProgressUpdateRequest,
    RoadmapResponse,
    SyllabusIngestRequest,
)
from app.services.embedding_service import EmbeddingService
from app.services.gpt_service import GPTTopicExtractor
from app.services.langgraph_workflow import build_ingest_workflow
from app.services.planner_service import PlannerService
from app.services.rag_service import RAGService
from app.services.resource_service import ResourceService
from app.services.topic_graph_service import TopicGraphService

router = APIRouter()

_repository: Optional[StudyRepository] = None


def get_repository(settings: Settings = Depends(get_settings)) -> StudyRepository:
    global _repository
    if _repository is None:
        _repository = StudyRepository(build_supabase_client(settings))
    return _repository


def get_topic_extractor(settings: Settings = Depends(get_settings)) -> GPTTopicExtractor:
    return GPTTopicExtractor(settings)


def get_embedding_service(settings: Settings = Depends(get_settings)) -> EmbeddingService:
    return EmbeddingService(settings)


def get_topic_graph_service(
    settings: Settings = Depends(get_settings),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> TopicGraphService:
    return TopicGraphService(settings, embedding_service)


def get_planner_service(settings: Settings = Depends(get_settings)) -> PlannerService:
    return PlannerService(settings)


def get_rag_service(settings: Settings = Depends(get_settings)) -> RAGService:
    return RAGService(settings)


def get_resource_service(settings: Settings = Depends(get_settings)) -> ResourceService:
    return ResourceService(settings)


def get_ingest_workflow(
    topic_extractor: GPTTopicExtractor = Depends(get_topic_extractor),
    rag_service: RAGService = Depends(get_rag_service),
    topic_graph_service: TopicGraphService = Depends(get_topic_graph_service),
    planner_service: PlannerService = Depends(get_planner_service),
    resource_service: ResourceService = Depends(get_resource_service),
):
    return build_ingest_workflow(topic_extractor, rag_service, topic_graph_service, planner_service, resource_service)


_PRIORITY_WEIGHT = {"High": 3, "Medium": 2, "Low": 1}


def _weighted_score(items) -> float:
    total_weight = 0.0
    earned_weight = 0.0
    for item in items:
        w = _PRIORITY_WEIGHT.get(item.priority, 1)
        total_weight += w
        if item.completed:
            earned_weight += w
        elif item.subtopics:
            done = sum(1 for s in item.subtopics if s.completed)
            earned_weight += w * done / len(item.subtopics)
    if not total_weight:
        return 0.0
    return round(earned_weight / total_weight * 100, 1)


def _storage_error(detail: str) -> HTTPException:
    return HTTPException(status_code=503, detail=detail)


@router.get("/health")
def healthcheck(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "service": settings.app_name}


@router.post("/syllabus/ingest", response_model=IngestResponse)
def ingest_syllabus(
    payload: SyllabusIngestRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    repository: StudyRepository = Depends(get_repository),
    workflow=Depends(get_ingest_workflow),
) -> IngestResponse:
    user_id = current_user.user_id
    result = workflow.invoke({
        "course_id": payload.course_id,
        "course_title": payload.course_title,
        "syllabus_text": payload.syllabus_text,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "difficulty_level": "medium",
        "raw_topics": [],
        "rag_index": None,
        "enriched_topics": [],
        "topic_graph": None,
        "resources": {},
        "roadmap": None,
    })
    graph = result["topic_graph"]
    roadmap = result["roadmap"]
    try:
        repository.save_course({
            "course_id": payload.course_id,
            "user_id": user_id,
            "course_title": payload.course_title,
            "start_date": payload.start_date.isoformat(),
            "end_date": (payload.end_date or (payload.start_date + timedelta(days=settings.default_planning_window_days - 1))).isoformat(),
            "difficulty_level": "medium",
        })
        repository.save_topic_graph(user_id, payload.course_id, graph)
        repository.save_roadmap(user_id, roadmap)
    except RepositoryError:
        raise _storage_error("Unable to persist generated roadmap.")
    return IngestResponse(roadmap=roadmap)


def _apply_completion(roadmap_items, completed: set):
    """Hydrate completed flags on items and subtopics; auto-complete topic when all subtopics done."""
    items = []
    for item in roadmap_items:
        updated_subs = [
            s.model_copy(update={"completed": s.id in completed})
            for s in item.subtopics
        ]
        topic_done = item.id in completed or (
            bool(updated_subs) and all(s.completed for s in updated_subs)
        )
        items.append(item.model_copy(update={"subtopics": updated_subs, "completed": topic_done}))
    return items


@router.post("/progress", response_model=dict)
def track_progress(
    payload: ProgressUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    repository: StudyRepository = Depends(get_repository),
) -> dict:
    user_id = current_user.user_id
    try:
        repository.save_progress(user_id, payload)
    except RepositoryError:
        raise _storage_error("Unable to save progress.")

    completed = repository.get_completed_topic_ids(user_id, payload.course_id)
    roadmap = repository.get_roadmap(user_id, payload.course_id)
    if not roadmap:
        return {"topic_id": payload.topic_id, "completed": payload.completed, "completion_score": 0.0}

    # auto-complete topic when all its subtopics are now done
    if payload.subtopic_id and payload.completed:
        topic_item = next((i for i in roadmap.items if i.id == payload.topic_id), None)
        if topic_item and topic_item.subtopics:
            all_sub_ids = {s.id for s in topic_item.subtopics}
            if all_sub_ids.issubset(completed):
                auto = ProgressUpdateRequest(
                    course_id=payload.course_id,
                    topic_id=payload.topic_id,
                    completed=True,
                )
                repository.save_progress(user_id, auto)
                completed = repository.get_completed_topic_ids(user_id, payload.course_id)

    items = _apply_completion(roadmap.items, completed)
    score = _weighted_score(items)
    return {"topic_id": payload.topic_id, "completed": payload.completed, "completion_score": score}


@router.get("/plan/{course_id}", response_model=RoadmapResponse)
def get_plan(
    course_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    repository: StudyRepository = Depends(get_repository),
) -> RoadmapResponse:
    user_id = current_user.user_id
    try:
        roadmap = repository.get_roadmap(user_id=user_id, course_id=course_id)
    except RepositoryError:
        raise _storage_error("Unable to load roadmap.")
    if roadmap is None:
        raise HTTPException(status_code=404, detail="Roadmap not found.")
    completed = repository.get_completed_topic_ids(user_id, course_id)
    items = _apply_completion(roadmap.items, completed)
    score = _weighted_score(items)
    return roadmap.model_copy(update={"items": items, "completion_score": score})
