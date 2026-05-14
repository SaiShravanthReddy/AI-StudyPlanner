from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.config import Settings, get_settings
from app.db.repository import RepositoryError, StudyRepository
from app.db.supabase_client import build_supabase_client
from app.schemas.planner import (
    IngestResponse,
    ProgressUpdateRequest,
    ReminderResponse,
    ReplanRequest,
    StudyPlanResponse,
    SyllabusIngestRequest,
)
from app.services.embedding_service import EmbeddingService
from app.services.gpt_service import GPTTopicExtractor
from app.services.langgraph_workflow import build_ingest_workflow, build_replan_workflow
from app.services.planner_service import PlannerService
from app.services.rag_service import RAGService
from app.services.reminder_service import ReminderService
from app.services.topic_graph_service import TopicGraphService

router = APIRouter()


def get_repository(settings: Settings = Depends(get_settings)) -> StudyRepository:
    return StudyRepository(build_supabase_client(settings))


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


def get_ingest_workflow(
    topic_extractor: GPTTopicExtractor = Depends(get_topic_extractor),
    rag_service: RAGService = Depends(get_rag_service),
    topic_graph_service: TopicGraphService = Depends(get_topic_graph_service),
    planner_service: PlannerService = Depends(get_planner_service),
):
    return build_ingest_workflow(topic_extractor, rag_service, topic_graph_service, planner_service)


def get_replan_workflow(
    planner_service: PlannerService = Depends(get_planner_service),
):
    return build_replan_workflow(planner_service)


def get_reminder_service(settings: Settings = Depends(get_settings)) -> ReminderService:
    return ReminderService(settings)


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
        "daily_study_minutes": payload.daily_study_minutes,
        "raw_topics": [],
        "rag_index": None,
        "enriched_topics": [],
        "topic_graph": None,
        "study_plan": None,
    })
    graph = result["topic_graph"]
    plan = result["study_plan"]
    try:
        repository.save_course(
            {
                "course_id": payload.course_id,
                "user_id": user_id,
                "course_title": payload.course_title,
                "start_date": payload.start_date.isoformat(),
                "end_date": (payload.end_date or (payload.start_date + timedelta(days=settings.default_planning_window_days - 1))).isoformat(),
                "daily_study_minutes": payload.daily_study_minutes,
            }
        )
        repository.save_topic_graph(user_id, payload.course_id, graph)
        repository.save_plan(user_id, plan)
    except RepositoryError:
        raise _storage_error("Unable to persist generated study plan.")
    return IngestResponse(graph=graph, plan=plan)


@router.post("/progress", response_model=dict)
def track_progress(
    payload: ProgressUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    repository: StudyRepository = Depends(get_repository),
) -> dict:
    user_id = current_user.user_id
    try:
        graph = repository.get_graph(user_id, payload.course_id)
    except RepositoryError:
        raise _storage_error("Unable to load course topics.")
    if graph is None:
        raise HTTPException(status_code=404, detail="Course topics not found.")
    try:
        repository.save_progress(user_id, payload)
    except RepositoryError:
        raise _storage_error("Unable to save progress.")
    return {"status": "saved", "course_id": payload.course_id, "topic_id": payload.topic_id}


@router.post("/plan/replan", response_model=StudyPlanResponse)
def replan(
    payload: ReplanRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    repository: StudyRepository = Depends(get_repository),
    workflow=Depends(get_replan_workflow),
) -> StudyPlanResponse:
    user_id = current_user.user_id
    try:
        graph = repository.get_graph(user_id, payload.course_id)
        completed_topic_ids = repository.get_completed_topic_ids(user_id, payload.course_id)
        existing_plan = repository.get_plan(user_id, payload.course_id)
    except RepositoryError:
        raise _storage_error("Unable to load plan data for replanning.")
    if graph is None:
        raise HTTPException(status_code=404, detail="Course topics not found.")
    result = workflow.invoke({
        "course_id": payload.course_id,
        "from_date": payload.from_date,
        "daily_study_minutes": payload.daily_study_minutes,
        "default_window_days": settings.default_planning_window_days,
        "topic_graph": graph,
        "completed_topic_ids": list(completed_topic_ids),
        "existing_plan": existing_plan,
        "horizon_end": None,
        "study_plan": None,
    })
    replanned = result["study_plan"]
    try:
        repository.save_plan(user_id, replanned)
    except RepositoryError:
        raise _storage_error("Unable to persist replanned study schedule.")
    return replanned


@router.get("/plan/{course_id}", response_model=StudyPlanResponse)
def get_plan(
    course_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    repository: StudyRepository = Depends(get_repository),
) -> StudyPlanResponse:
    user_id = current_user.user_id
    try:
        plan = repository.get_plan(user_id=user_id, course_id=course_id)
    except RepositoryError:
        raise _storage_error("Unable to load study plan.")
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    return plan


@router.get("/progress/{course_id}", response_model=list[dict])
def get_progress(
    course_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    repository: StudyRepository = Depends(get_repository),
) -> list[dict]:
    user_id = current_user.user_id
    try:
        return repository.get_progress_rows(user_id=user_id, course_id=course_id)
    except RepositoryError:
        raise _storage_error("Unable to load progress history.")


@router.get("/reminders/{course_id}", response_model=ReminderResponse)
def get_reminders(
    course_id: str,
    day: Optional[date] = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
    repository: StudyRepository = Depends(get_repository),
    reminder_service: ReminderService = Depends(get_reminder_service),
) -> ReminderResponse:
    user_id = current_user.user_id
    try:
        plan = repository.get_plan(user_id=user_id, course_id=course_id)
    except RepositoryError:
        raise _storage_error("Unable to load reminders.")
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    reminders = reminder_service.build_daily_reminders(plan, for_day=day)
    return ReminderResponse(reminders=reminders)
