"""Helper to create a Supabase client when credentials are provided."""

from __future__ import annotations

import os
from typing import Optional

from ..utils.logging import get_logger

LOGGER = get_logger("db.supabase")


def create_supabase_client():  # pragma: no cover - optional dependency
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        LOGGER.info("Supabase credentials not configured; skipping client creation")
        return None
    try:
        from supabase import create_client  # type: ignore

        return create_client(url, key)
    except Exception as exc:
        LOGGER.error("Failed to create Supabase client: %s", exc)
        return None

