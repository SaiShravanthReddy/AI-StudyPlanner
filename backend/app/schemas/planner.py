from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class TopicNode(BaseModel):
    id: str
    title: str
    subtopics: list[str] = Field(default_factory=list)
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


class ResourceSuggestion(BaseModel):
    article_title: Optional[str] = None
    article_url: Optional[str] = None
    video_title: Optional[str] = None
    video_url: Optional[str] = None


class SubtopicItem(BaseModel):
    id: str
    title: str
    resources: Optional[ResourceSuggestion] = None
    completed: bool = False


class RoadmapItem(BaseModel):
    id: str
    topic: str
    subtopics: list[SubtopicItem] = Field(default_factory=list)
    date: date
    suggested_minutes: int
    difficulty: str  # "Low", "Medium", "High"
    priority: str   # "High", "Medium", "Low"
    dependency: Optional[str] = None
    resources: Optional[ResourceSuggestion] = None
    completed: bool = False


class RoadmapResponse(BaseModel):
    course_id: str
    generated_at: datetime
    items: list[RoadmapItem]
    completion_score: float = 0.0


class SyllabusIngestRequest(BaseModel):
    course_id: str
    course_title: str
    syllabus_text: str = Field(min_length=10)
    start_date: date
    end_date: Optional[date] = None


class IngestResponse(BaseModel):
    roadmap: RoadmapResponse


class ProgressUpdateRequest(BaseModel):
    course_id: str
    topic_id: str
    subtopic_id: Optional[str] = None
    completed: bool
