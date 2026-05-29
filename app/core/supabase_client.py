from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings
from app.core.exceptions import service_unavailable


@lru_cache
def get_supabase() -> Client:
    """Return a cached Supabase client using the service role key.

    The service role key is required for server-side writes and storage
    uploads (it bypasses Row Level Security). Falls back to the anon key
    if a service key is not provided.
    """
    settings = get_settings()
    if not settings.is_configured:
        raise service_unavailable(
            "Supabase is not configured. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_KEY (or SUPABASE_ANON_KEY) environment variables."
        )
    key = settings.supabase_service_key or settings.supabase_anon_key
    return create_client(settings.supabase_url, key)
