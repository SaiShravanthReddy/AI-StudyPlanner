from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class TopicNode(BaseModel):
    id: str
    title: str
    description: str = ""
    difficulty: int = Field(default=3, ge=1, le=5)
    estimated_minutes: int = Field(default=60, ge=15, le=600)
    dependencies: list[str] = Field(default_factory=list)
    similarity_links: list[str] = Field(default_factory=list)


class TopicEdge(BaseModel):
    source: str
    target: str
    edge_type: str = "dependency"
    weight: float = 0.0


class TopicGraphResponse(BaseModel):
    course_id: str
    topics: list[TopicNode]
    edges: list[TopicEdge]


class DailyPlanItem(BaseModel):
    date: date
    topic_id: str
    topic_title: str
    planned_minutes: int = Field(ge=15)
    status: str = "pending"
    rationale: str = ""


class StudyPlanResponse(BaseModel):
    course_id: str
    user_id: str
    generated_at: datetime
    items: list[DailyPlanItem]


class IngestResponse(BaseModel):
    graph: TopicGraphResponse
    plan: StudyPlanResponse


class SyllabusIngestRequest(BaseModel):
    user_id: str
    course_id: str
    course_title: str
    syllabus_text: str = Field(min_length=50)
    start_date: date
    end_date: Optional[date] = None
    daily_study_minutes: int = Field(default=120, ge=30, le=480)


class ProgressUpdateRequest(BaseModel):
    user_id: str
    course_id: str
    topic_id: str
    date: date
    minutes_spent: int = Field(default=0, ge=0, le=1440)
    completed: bool = False


class ReplanRequest(BaseModel):
    user_id: str
    course_id: str
    from_date: date
    daily_study_minutes: int = Field(default=120, ge=30, le=480)


class ReminderResponse(BaseModel):
    user_id: str
    reminders: list[str]
