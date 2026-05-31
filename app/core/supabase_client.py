import base64
import json
import os
from functools import lru_cache

from fastapi import Header, HTTPException
from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

from app.core.config import get_settings
from app.core.exceptions import service_unavailable


def _service_role_key(settings) -> str:
    """Resolve service role key (Vercel/Supabase docs often use SUPABASE_SERVICE_ROLE_KEY)."""
    return (
        settings.supabase_service_key.strip()
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    )


def _jwt_role(key: str) -> str | None:
    """Read the ``role`` claim from a Supabase JWT without verifying signature."""
    try:
        payload = key.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        return data.get("role")
    except Exception:  # noqa: BLE001
        return None


def parse_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return authorization.split(" ", 1)[1].strip()


@lru_cache
def get_supabase_auth() -> Client:
    """Anon key client — use for ``sign_in_with_password`` and ``auth.get_user``."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise service_unavailable("SUPABASE_URL and SUPABASE_ANON_KEY are required.")
    return create_client(settings.supabase_url, settings.supabase_anon_key)


@lru_cache
def get_supabase() -> Client:
    """Service-role client — admin auth, catalog reads, profile joins (bypasses RLS)."""
    settings = get_settings()
    if not settings.is_configured:
        raise service_unavailable(
            "Supabase is not configured. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_KEY (service_role JWT)."
        )
    service = _service_role_key(settings)
    if not service or _jwt_role(service) != "service_role":
        raise service_unavailable(
            "SUPABASE_SERVICE_KEY must be the service_role JWT from Supabase (Legacy API keys)."
        )
    return create_client(settings.supabase_url, service)


def get_supabase_as_user(access_token: str) -> Client:
    """Supabase client scoped to the logged-in user (respects RLS)."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise service_unavailable("Supabase anon key is required for owner writes.")
    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        options=ClientOptions(
            headers={"Authorization": f"Bearer {access_token}"},
            auto_refresh_token=False,
            persist_session=False,
        ),
    )


def get_supabase_for_writes(authorization: str | None = Header(default=None)) -> Client:
    """DB client for inserts/updates — service_role if configured, else user JWT + RLS."""
    settings = get_settings()
    service = _service_role_key(settings)
    if service and _jwt_role(service) == "service_role":
        return create_client(settings.supabase_url, service)
    token = parse_bearer_token(authorization)
    return get_supabase_as_user(token)
