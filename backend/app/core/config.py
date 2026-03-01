from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI-Powered Adaptive Study Planner"
    api_v1_prefix: str = "/api/v1"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    sentence_model_name: str = "all-MiniLM-L6-v2"
    topic_similarity_threshold: float = 0.62
    default_planning_window_days: int = 14
    supabase_url: str | None = None
    supabase_service_key: str | None = None
    timezone: str = "America/New_York"
    reminder_sender: str = "planner-bot"
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
