from fastapi import Header, HTTPException

from app.core.supabase_http import (
    SupabaseRest,
    get_anon_client,
    get_service_client,
    get_user_client,
    jwt_role,
    _service_role_key,
)
from app.core.config import get_settings


def parse_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return authorization.split(" ", 1)[1].strip()


def get_supabase() -> SupabaseRest:
    """Service-role client — admin auth, catalog reads, profile joins (bypasses RLS)."""
    return get_service_client()


def get_supabase_auth() -> SupabaseRest:
    """Anon key client — use for sign-in."""
    return get_anon_client()


def get_supabase_as_user(access_token: str) -> SupabaseRest:
    """Supabase client scoped to the logged-in user (respects RLS)."""
    return get_user_client(access_token)


async def get_supabase_for_writes(
    authorization: str | None = Header(default=None),
) -> SupabaseRest:
    """DB client for inserts/updates — service_role if configured, else user JWT + RLS."""
    settings = get_settings()
    service = _service_role_key(settings)
    if service and jwt_role(service) == "service_role":
        return get_service_client()
    token = parse_bearer_token(authorization)
    return get_user_client(token)
