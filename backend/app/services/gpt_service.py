import json
import logging
import re
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class TopicDraft:
    title: str
    subtopics: list[str]
    description: str
    difficulty: int
    estimated_minutes: int
    dependencies: list[str]


class GPTTopicExtractor:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._llm = (
            ChatOpenAI(model=settings.openai_model, temperature=0.2, api_key=settings.openai_api_key)
            if settings.openai_api_key
            else None
        )

    def extract_topics(self, syllabus_text: str, course_title: str) -> list[TopicDraft]:
        if not self._llm:
            return self._fallback_topics(syllabus_text)
        try:
            return self._extract_with_gpt(syllabus_text, course_title)
        except Exception:
            logger.exception("Falling back to heuristic topic extraction", extra={"course_title": course_title})
            return self._fallback_topics(syllabus_text)

    def _extract_with_gpt(self, syllabus_text: str, course_title: str) -> list[TopicDraft]:
        system_prompt = (
            "You are an academic planning assistant. For each syllabus entry:\n"
            "1. Write a SHORT 'title' — a clean rephrased name for the overall topic (3-7 words, NOT a copy of the raw syllabus text).\n"
            "2. Write 'subtopics' — an array of INDIVIDUAL concepts the student must learn. "
            "   Rules for subtopics:\n"
            "   - Each subtopic is ONE specific concept or skill, written as a noun phrase (e.g. 'ReLU activation function').\n"
            "   - NEVER copy the full syllabus entry as a subtopic.\n"
            "   - If the entry lists multiple things separated by semicolons or commas, each becomes its own subtopic.\n"
            "   - Add 1-2 prerequisite micro-concepts if they are needed to understand the entry.\n"
            "   - Aim for 3-6 subtopics per topic.\n"
            "   Example: 'The vanishing gradient problem; ReLU, Leaky ReLU, Soft-Max' becomes\n"
            "     title='Activation Functions and Gradient Problems',\n"
            "     subtopics=['Vanishing gradient problem', 'ReLU activation function', "
            "'Leaky ReLU activation function', 'Softmax activation function', 'Gradient flow in deep networks'].\n"
            "3. In 'dependencies', list only OTHER topic titles the student must understand first.\n"
            "Ignore the input order — use subject-matter knowledge to set prerequisites.\n"
            "Return strict JSON only:\n"
            '{"topics":[{"title":"","subtopics":[""],"description":"","difficulty":1-5,"estimated_minutes":30-240,"dependencies":["title"]}]}\n'
            "No markdown, no extra keys."
        )
        user_prompt = (
            f"Course: {course_title}\n\nSyllabus:\n{syllabus_text}\n\n"
            "Return 8-20 topics. Output order does not matter."
        )
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        response = self._llm.invoke(messages)
        payload = self._coerce_json(response.content or "")
        topics = payload.get("topics", [])
        parsed = []
        for raw in topics:
            title = str(raw.get("title", "")).strip()
            if not title:
                continue
            parsed.append(
                TopicDraft(
                    title=title,
                    subtopics=[str(s).strip() for s in raw.get("subtopics", []) if str(s).strip()],
                    description=str(raw.get("description", "")).strip(),
                    difficulty=self._clamp_int(raw.get("difficulty", 3), 1, 5, 3),
                    estimated_minutes=self._clamp_int(raw.get("estimated_minutes", 60), 30, 360, 60),
                    dependencies=[str(dep).strip() for dep in raw.get("dependencies", []) if str(dep).strip()],
                )
            )
        if not parsed:
            return self._fallback_topics(syllabus_text)
        return parsed

    def _coerce_json(self, content: str) -> dict:
        content = content.strip()
        if not content:
            return {}
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if not match:
                return {}
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}

    def _fallback_topics(self, syllabus_text: str) -> list[TopicDraft]:
        lines = []
        for raw in syllabus_text.splitlines():
            stripped = raw.strip(" -*\t")
            if 15 <= len(stripped) <= 140:
                lines.append(stripped)
        if not lines:
            fragments = [chunk.strip() for chunk in re.split(r"[.;\n]+", syllabus_text) if chunk.strip()]
            lines = [x for x in fragments if 15 <= len(x) <= 140]
        lines = lines[:12]
        topics = []
        for idx, line in enumerate(lines):
            difficulty = 2 + min(3, idx // 3)
            topics.append(
                TopicDraft(
                    title=self._titleize(line, idx),
                    subtopics=self._split_subtopics(line),
                    description=line,
                    difficulty=difficulty,
                    estimated_minutes=45 + difficulty * 20,
                    dependencies=[topics[idx - 1].title] if idx > 0 else [],
                )
            )
        if topics:
            return topics
        return [
            TopicDraft(
                title="Course Foundations",
                subtopics=["Review course objectives", "Identify key concepts"],
                description="Initial overview and foundational concepts.",
                difficulty=2,
                estimated_minutes=60,
                dependencies=[],
            ),
            TopicDraft(
                title="Core Techniques",
                subtopics=["Study primary methods", "Solve practice problems"],
                description="Primary methods and practical problem-solving patterns.",
                difficulty=3,
                estimated_minutes=90,
                dependencies=["Course Foundations"],
            ),
        ]

    def _split_subtopics(self, line: str) -> list[str]:
        """Split a raw syllabus line like 'A; B, C' into individual concept strings."""
        parts = []
        for segment in re.split(r";", line):
            for chunk in re.split(r",", segment):
                cleaned = chunk.strip(" -*\t")
                if len(cleaned) >= 3:
                    parts.append(cleaned)
        return parts if parts else [line]

    def _titleize(self, raw: str, idx: int) -> str:
        cleaned = re.sub(r"^[0-9\W_]+", "", raw).strip()
        if not cleaned:
            return f"Topic {idx + 1}"
        words = cleaned.split()
        title = " ".join(words[:8]).strip()
        return title if len(title) >= 5 else f"Topic {idx + 1}"

    def _clamp_int(self, value: object, low: int, high: int, default: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return default
        return max(low, min(high, number))
