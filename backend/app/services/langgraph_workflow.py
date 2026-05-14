"""LangGraph orchestration for syllabus ingestion workflow.

Ingest pipeline (parallel fan-out):
    START ──► extract_topics ──► enrich_topics ──► build_graph ──► generate_roadmap ──► END
         └──► build_rag_index ──►
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.services.gpt_service import GPTTopicExtractor, TopicDraft
from app.services.planner_service import PlannerService
from app.services.rag_service import RAGService
from app.services.resource_service import ResourceService
from app.services.topic_graph_service import TopicGraphService

logger = logging.getLogger(__name__)


class IngestState(TypedDict):
    """Mutable state flowing through the syllabus-ingestion pipeline."""

    # ── inputs ──────────────────────────────────────────────────────────────
    course_id: str
    course_title: str
    syllabus_text: str
    start_date: date
    end_date: Optional[date]
    difficulty_level: str  # "easy" | "medium" | "hard"

    # ── intermediate ────────────────────────────────────────────────────────
    raw_topics: list        # list[TopicDraft]
    rag_index: Any          # FAISS vectorstore | None
    enriched_topics: list   # list[TopicDraft]
    topic_graph: Any        # TopicGraphResponse | None
    resources: dict         # topic_title -> ResourceSuggestion

    # ── output ──────────────────────────────────────────────────────────────
    roadmap: Any            # RoadmapResponse | None


def build_ingest_workflow(
    topic_extractor: GPTTopicExtractor,
    rag_service: RAGService,
    topic_graph_service: TopicGraphService,
    planner_service: PlannerService,
    resource_service: ResourceService,
) -> Any:
    """Compile and return the syllabus-ingestion LangGraph workflow."""

    def extract_topics_node(state: IngestState) -> dict:
        topics = topic_extractor.extract_topics(state["syllabus_text"], state["course_title"])
        logger.debug("extract_topics: extracted %d topics", len(topics))
        return {"raw_topics": topics}

    def build_rag_index_node(state: IngestState) -> dict:
        index = rag_service.build_index(state["syllabus_text"])
        logger.debug("build_rag_index: index built=%s", index is not None)
        return {"rag_index": index}

    def enrich_topics_node(state: IngestState) -> dict:
        index = state.get("rag_index")
        topics: list[TopicDraft] = state.get("raw_topics") or []
        if index is None:
            return {"enriched_topics": topics}

        enriched: list[TopicDraft] = []
        for topic in topics:
            chunks = rag_service.retrieve(index, f"{topic.title}: {topic.description}")
            if chunks:
                context_snippet = " ".join(chunks[:2])[:200]
                enriched.append(TopicDraft(
                    title=topic.title,
                    description=f"{topic.description} [Context: {context_snippet}]",
                    difficulty=topic.difficulty,
                    estimated_minutes=topic.estimated_minutes,
                    dependencies=topic.dependencies,
                ))
            else:
                enriched.append(topic)
        return {"enriched_topics": enriched}

    def build_graph_node(state: IngestState) -> dict:
        topics = state.get("enriched_topics") or state.get("raw_topics") or []
        graph = topic_graph_service.build_topic_graph(state["course_id"], topics)
        return {"topic_graph": graph}

    def suggest_resources_node(state: IngestState) -> dict:
        topics = (state.get("topic_graph").topics if state.get("topic_graph") else [])
        resources = resource_service.suggest_resources(
            topic_titles=[t.title for t in topics],
            course_title=state["course_title"],
        )
        return {"resources": resources}

    def generate_roadmap_node(state: IngestState) -> dict:
        roadmap = planner_service.generate_roadmap(
            course_id=state["course_id"],
            topics=state["topic_graph"].topics,
            start_date=state["start_date"],
            end_date=state["end_date"],
            difficulty_level=state["difficulty_level"],
            resources=state.get("resources", {}),
        )
        return {"roadmap": roadmap}

    builder: StateGraph = StateGraph(IngestState)
    builder.add_node("extract_topics", extract_topics_node)
    builder.add_node("build_rag_index", build_rag_index_node)
    builder.add_node("enrich_topics", enrich_topics_node)
    builder.add_node("build_graph", build_graph_node)
    builder.add_node("suggest_resources", suggest_resources_node)
    builder.add_node("generate_roadmap", generate_roadmap_node)

    builder.add_edge(START, "extract_topics")
    builder.add_edge(START, "build_rag_index")
    builder.add_edge("extract_topics", "enrich_topics")
    builder.add_edge("build_rag_index", "enrich_topics")
    builder.add_edge("enrich_topics", "build_graph")
    builder.add_edge("build_graph", "suggest_resources")
    builder.add_edge("suggest_resources", "generate_roadmap")
    builder.add_edge("generate_roadmap", END)

    return builder.compile()
