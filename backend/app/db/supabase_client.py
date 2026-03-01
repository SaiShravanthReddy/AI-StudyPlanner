from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

from app.core.config import Settings

if TYPE_CHECKING:
    from supabase import Client
else:
    Client = Any


def build_supabase_client(settings: Settings) -> Optional[Client]:
    if not settings.supabase_url or not settings.supabase_service_key:
        return None
    try:
        from supabase import create_client

        return create_client(settings.supabase_url, settings.supabase_service_key)
    except Exception:
        return None
