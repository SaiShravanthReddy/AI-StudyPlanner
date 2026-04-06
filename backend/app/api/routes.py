from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.config import get_settings
from app.db.repository import StudyRepository
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
from app.services.planner_service import PlannerService
from app.services.reminder_service import ReminderService
from app.services.topic_graph_service import TopicGraphService

router = APIRouter()
settings = get_settings()
repository = StudyRepository(build_supabase_client(settings))
topic_extractor = GPTTopicExtractor(settings)
embedding_service = EmbeddingService(settings)
topic_graph_service = TopicGraphService(settings, embedding_service)
planner_service = PlannerService(settings)
reminder_service = ReminderService()


@router.get("/health")
def healthcheck() -> dict:
    return {"status": "ok", "service": settings.app_name}


@router.post("/syllabus/ingest", response_model=IngestResponse)
def ingest_syllabus(
    payload: SyllabusIngestRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> IngestResponse:
    if payload.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden for requested user.")
    topic_drafts = topic_extractor.extract_topics(payload.syllabus_text, payload.course_title)
    graph = topic_graph_service.build_topic_graph(payload.course_id, topic_drafts)
    plan = planner_service.generate_plan(
        user_id=payload.user_id,
        course_id=payload.course_id,
        topics=graph.topics,
        start_date=payload.start_date,
        end_date=payload.end_date,
        daily_study_minutes=payload.daily_study_minutes,
    )
    repository.save_course(
        {
            "course_id": payload.course_id,
            "user_id": payload.user_id,
            "course_title": payload.course_title,
            "start_date": payload.start_date.isoformat(),
            "end_date": (payload.end_date or (payload.start_date + timedelta(days=settings.default_planning_window_days - 1))).isoformat(),
            "daily_study_minutes": payload.daily_study_minutes,
        }
    )
    repository.save_topic_graph(payload.user_id, payload.course_id, graph)
    repository.save_plan(plan)
    return IngestResponse(graph=graph, plan=plan)


@router.post("/progress", response_model=dict)
def track_progress(
    payload: ProgressUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    if payload.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden for requested user.")
    graph = repository.get_graph(payload.user_id, payload.course_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Course topics not found.")
    repository.save_progress(payload)
    return {"status": "saved", "course_id": payload.course_id, "topic_id": payload.topic_id}


@router.post("/plan/replan", response_model=StudyPlanResponse)
def replan(
    payload: ReplanRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> StudyPlanResponse:
    if payload.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden for requested user.")
    graph = repository.get_graph(payload.user_id, payload.course_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Course topics not found.")
    completed_topic_ids = repository.get_completed_topic_ids(payload.user_id, payload.course_id)
    existing_plan = repository.get_plan(payload.user_id, payload.course_id)
    if existing_plan and existing_plan.items:
        horizon_end = max(item.date for item in existing_plan.items)
    else:
        horizon_end = payload.from_date + timedelta(days=settings.default_planning_window_days - 1)
    replanned = planner_service.generate_plan(
        user_id=payload.user_id,
        course_id=payload.course_id,
        topics=graph.topics,
        start_date=payload.from_date,
        end_date=horizon_end,
        daily_study_minutes=payload.daily_study_minutes,
        completed_topic_ids=completed_topic_ids,
    )
    repository.save_plan(replanned)
    return replanned


@router.get("/plan/{user_id}/{course_id}", response_model=StudyPlanResponse)
def get_plan(
    user_id: str,
    course_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> StudyPlanResponse:
    if user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden for requested user.")
    plan = repository.get_plan(user_id=user_id, course_id=course_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    return plan


@router.get("/progress/{user_id}/{course_id}", response_model=list[dict])
def get_progress(
    user_id: str,
    course_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[dict]:
    if user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden for requested user.")
    return repository.get_progress_rows(user_id=user_id, course_id=course_id)


@router.get("/reminders/{user_id}/{course_id}", response_model=ReminderResponse)
def get_reminders(
    user_id: str,
    course_id: str,
    day: Optional[date] = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ReminderResponse:
    if user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden for requested user.")
    plan = repository.get_plan(user_id=user_id, course_id=course_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    reminders = reminder_service.build_daily_reminders(plan, for_day=day)
    return ReminderResponse(user_id=user_id, reminders=reminders)
