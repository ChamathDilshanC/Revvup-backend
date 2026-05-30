import os
from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings
from app.core.exceptions import service_unavailable


def _service_role_key(settings) -> str:
    """Resolve service role key (Vercel/Supabase docs often use SUPABASE_SERVICE_ROLE_KEY)."""
    return (
        settings.supabase_service_key.strip()
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    )


@lru_cache
def get_supabase() -> Client:
    """Return a cached Supabase client using the service role key.

    The service role key is required for server-side writes and storage
    uploads (it bypasses Row Level Security). Falls back to the anon key
    only when no service key is set (inserts may fail under RLS).
    """
    settings = get_settings()
    if not settings.is_configured:
        raise service_unavailable(
            "Supabase is not configured. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_KEY (or SUPABASE_ANON_KEY) environment variables."
        )
    key = _service_role_key(settings) or settings.supabase_anon_key
    return create_client(settings.supabase_url, key)
