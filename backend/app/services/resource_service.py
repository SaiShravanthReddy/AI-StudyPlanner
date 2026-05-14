from __future__ import annotations

import json
import logging
import re
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import Settings
from app.schemas.planner import ResourceSuggestion

logger = logging.getLogger(__name__)


class ResourceService:
    def __init__(self, settings: Settings):
        self._llm = (
            ChatOpenAI(model=settings.openai_model, temperature=0.0, api_key=settings.openai_api_key)
            if settings.openai_api_key
            else None
        )

    def suggest_resources(self, topic_titles: list[str], course_title: str) -> dict[str, ResourceSuggestion]:
        if not self._llm or not topic_titles:
            return {}
        try:
            return self._fetch(topic_titles, course_title)
        except Exception:
            logger.exception("Resource suggestion failed; returning empty")
            return {}

    def _fetch(self, topic_titles: list[str], course_title: str) -> dict[str, ResourceSuggestion]:
        topics_list = "\n".join(f"- {t}" for t in topic_titles)
        system_prompt = (
            "You are an educational resource curator. For each topic, suggest ONE article and ONE YouTube video "
            "that you are highly confident exist and are publicly accessible. Only suggest URLs you are certain about — "
            "prefer Wikipedia, official documentation, and well-known YouTube educators. "
            "If you are not confident a specific resource exists for a topic, use null for that field. "
            "Return strict JSON only: "
            '{"resources": [{"topic": "<exact topic title>", '
            '"article_title": "<title or null>", "article_url": "<https://... or null>", '
            '"video_title": "<title or null>", "video_url": "<https://youtube.com/... or null>"}]}'
        )
        user_prompt = (
            f"Course: {course_title}\n\nTopics:\n{topics_list}\n\n"
            "Return one entry per topic in the same order."
        )
        response = self._llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
        raw = self._parse_json(response.content or "")
        result: dict[str, ResourceSuggestion] = {}
        for entry in raw.get("resources", []):
            topic = str(entry.get("topic", "")).strip()
            if not topic:
                continue
            result[topic] = ResourceSuggestion(
                article_title=entry.get("article_title") or None,
                article_url=self._valid_url(entry.get("article_url")),
                video_title=entry.get("video_title") or None,
                video_url=self._valid_url(entry.get("video_url"), require_youtube=True),
            )
        return result

    def _valid_url(self, value: object, require_youtube: bool = False) -> Optional[str]:
        if not value or not isinstance(value, str):
            return None
        url = value.strip()
        if not url.startswith("https://"):
            return None
        if require_youtube and "youtube.com" not in url and "youtu.be" not in url:
            return None
        return url

    def _parse_json(self, content: str) -> dict:
        content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        return {}
