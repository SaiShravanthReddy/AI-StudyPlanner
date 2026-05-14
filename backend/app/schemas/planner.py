from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DifficultyLevel(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


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


class RoadmapItem(BaseModel):
    id: str
    topic: str
    subtopic: Optional[str] = None
    date: date
    suggested_minutes: int
    difficulty: str  # "Low", "Medium", "High"
    priority: str   # "High", "Medium", "Low"
    dependency: Optional[str] = None  # display title of first prerequisite
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
    difficulty_level: DifficultyLevel = DifficultyLevel.medium


class IngestResponse(BaseModel):
    roadmap: RoadmapResponse


class ProgressUpdateRequest(BaseModel):
    course_id: str
    topic_id: str
    completed: bool
