"""LangGraph orchestration for syllabus ingestion and adaptive replanning workflows.

Ingest pipeline (parallel fan-out):
    START ──► extract_topics ──► enrich_topics ──► build_graph ──► generate_plan ──► END
         └──► build_rag_index ──►

Replan pipeline (sequential):
    START ──► resolve_horizon ──► generate_replan ──► END
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.services.gpt_service import GPTTopicExtractor, TopicDraft
from app.services.planner_service import PlannerService
from app.services.rag_service import RAGService
from app.services.topic_graph_service import TopicGraphService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State schemas
# ---------------------------------------------------------------------------


class IngestState(TypedDict):
    """Mutable state flowing through the syllabus-ingestion pipeline."""

    # ── inputs ──────────────────────────────────────────────────────────────
    course_id: str
    course_title: str
    syllabus_text: str
    start_date: date
    end_date: date | None
    daily_study_minutes: int

    # ── intermediate ────────────────────────────────────────────────────────
    raw_topics: list        # list[TopicDraft] — filled by extract_topics node
    rag_index: Any          # FAISS vectorstore | None — filled by build_rag_index node
    enriched_topics: list   # list[TopicDraft] — filled by enrich_topics node
    topic_graph: Any        # TopicGraphResponse | None — filled by build_graph node

    # ── output ──────────────────────────────────────────────────────────────
    study_plan: Any         # StudyPlanResponse | None — filled by generate_plan node


class ReplanState(TypedDict):
    """Mutable state flowing through the adaptive replanning pipeline."""

    # ── inputs ──────────────────────────────────────────────────────────────
    course_id: str
    from_date: date
    daily_study_minutes: int
    default_window_days: int
    topic_graph: Any        # TopicGraphResponse fetched before workflow starts
    completed_topic_ids: list[str]
    existing_plan: Any      # StudyPlanResponse | None — used for horizon calculation

    # ── intermediate ────────────────────────────────────────────────────────
    horizon_end: date | None

    # ── output ──────────────────────────────────────────────────────────────
    study_plan: Any         # StudyPlanResponse — filled by generate_replan node


# ---------------------------------------------------------------------------
# Ingest workflow
# ---------------------------------------------------------------------------


def build_ingest_workflow(
    topic_extractor: GPTTopicExtractor,
    rag_service: RAGService,
    topic_graph_service: TopicGraphService,
    planner_service: PlannerService,
) -> Any:
    """Compile and return the syllabus-ingestion LangGraph workflow.

    ``extract_topics`` and ``build_rag_index`` run in parallel from START.
    Both results are available when ``enrich_topics`` executes, allowing RAG
    context to augment the LLM-extracted topic descriptions before planning.
    """

    def extract_topics_node(state: IngestState) -> dict:
        topics = topic_extractor.extract_topics(state["syllabus_text"], state["course_title"])
        logger.debug("extract_topics: extracted %d topics", len(topics))
        return {"raw_topics": topics}

    def build_rag_index_node(state: IngestState) -> dict:
        index = rag_service.build_index(state["syllabus_text"])
        logger.debug("build_rag_index: index built=%s", index is not None)
        return {"rag_index": index}

    def enrich_topics_node(state: IngestState) -> dict:
        """Augment each topic description with the most relevant syllabus chunks."""
        index = state.get("rag_index")
        topics: list[TopicDraft] = state.get("raw_topics") or []
        if index is None:
            # RAG unavailable — pass topics through unchanged
            return {"enriched_topics": topics}

        enriched: list[TopicDraft] = []
        for topic in topics:
            chunks = rag_service.retrieve(index, f"{topic.title}: {topic.description}")
            if chunks:
                context_snippet = " ".join(chunks[:2])[:200]
                enriched.append(
                    TopicDraft(
                        title=topic.title,
                        description=f"{topic.description} [Context: {context_snippet}]",
                        difficulty=topic.difficulty,
                        estimated_minutes=topic.estimated_minutes,
                        dependencies=topic.dependencies,
                    )
                )
            else:
                enriched.append(topic)
        logger.debug("enrich_topics: enriched %d/%d topics via RAG", sum(1 for t in enriched if "[Context:" in t.description), len(enriched))
        return {"enriched_topics": enriched}

    def build_graph_node(state: IngestState) -> dict:
        topics = state.get("enriched_topics") or state.get("raw_topics") or []
        graph = topic_graph_service.build_topic_graph(state["course_id"], topics)
        return {"topic_graph": graph}

    def generate_plan_node(state: IngestState) -> dict:
        plan = planner_service.generate_plan(
            course_id=state["course_id"],
            topics=state["topic_graph"].topics,
            start_date=state["start_date"],
            end_date=state["end_date"],
            daily_study_minutes=state["daily_study_minutes"],
        )
        return {"study_plan": plan}

    builder: StateGraph = StateGraph(IngestState)
    builder.add_node("extract_topics", extract_topics_node)
    builder.add_node("build_rag_index", build_rag_index_node)
    builder.add_node("enrich_topics", enrich_topics_node)
    builder.add_node("build_graph", build_graph_node)
    builder.add_node("generate_plan", generate_plan_node)

    # Parallel fan-out: both extract_topics and build_rag_index start from START
    # and converge at enrich_topics (LangGraph waits for both before proceeding).
    builder.add_edge(START, "extract_topics")
    builder.add_edge(START, "build_rag_index")
    builder.add_edge("extract_topics", "enrich_topics")
    builder.add_edge("build_rag_index", "enrich_topics")
    builder.add_edge("enrich_topics", "build_graph")
    builder.add_edge("build_graph", "generate_plan")
    builder.add_edge("generate_plan", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# Replan workflow
# ---------------------------------------------------------------------------


def build_replan_workflow(planner_service: PlannerService) -> Any:
    """Compile and return the adaptive replanning LangGraph workflow.

    Resolves the planning horizon from the existing plan (or default window),
    then regenerates the schedule respecting completed topics and deadlines.
    """

    def resolve_horizon_node(state: ReplanState) -> dict:
        existing_plan = state.get("existing_plan")
        if existing_plan and existing_plan.items:
            horizon_end = max(item.date for item in existing_plan.items)
        else:
            horizon_end = state["from_date"] + timedelta(days=state["default_window_days"] - 1)
        logger.debug("resolve_horizon: horizon_end=%s", horizon_end)
        return {"horizon_end": horizon_end}

    def generate_replan_node(state: ReplanState) -> dict:
        plan = planner_service.generate_plan(
            course_id=state["course_id"],
            topics=state["topic_graph"].topics,
            start_date=state["from_date"],
            end_date=state["horizon_end"],
            daily_study_minutes=state["daily_study_minutes"],
            completed_topic_ids=set(state.get("completed_topic_ids") or []),
        )
        return {"study_plan": plan}

    builder: StateGraph = StateGraph(ReplanState)
    builder.add_node("resolve_horizon", resolve_horizon_node)
    builder.add_node("generate_replan", generate_replan_node)

    builder.add_edge(START, "resolve_horizon")
    builder.add_edge("resolve_horizon", "generate_replan")
    builder.add_edge("generate_replan", END)

    return builder.compile()
