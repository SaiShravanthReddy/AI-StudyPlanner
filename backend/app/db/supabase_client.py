from __future__ import annotations

import logging
from typing import Any, Optional, TYPE_CHECKING

from app.core.config import Settings

logger = logging.getLogger(__name__)

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
        logger.exception("Failed to initialize Supabase client")
        return None
