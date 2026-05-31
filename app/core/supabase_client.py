import asyncio
import base64
import json
import os

import httpx
from fastapi import Header, HTTPException
from httpx import AsyncClient as HttpxAsyncClient
from httpx import Limits, Timeout
from supabase import AsyncClient, acreate_client
from supabase.lib.client_options import AsyncClientOptions as ClientOptions

from app.core.config import get_settings
from app.core.exceptions import service_unavailable

_service_client: AsyncClient | None = None
_auth_client: AsyncClient | None = None
_client_lock = asyncio.Lock()
_shared_httpx: HttpxAsyncClient | None = None


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


def _get_shared_httpx() -> HttpxAsyncClient:
    global _shared_httpx
    if _shared_httpx is None:
        _shared_httpx = HttpxAsyncClient(
            limits=Limits(max_connections=10, max_keepalive_connections=0),
            timeout=Timeout(30.0, connect=10.0),
        )
    return _shared_httpx


def _client_options(**header_overrides: str) -> ClientOptions:
    options = ClientOptions(
        auto_refresh_token=False,
        persist_session=False,
        httpx_client=_get_shared_httpx(),
    )
    if header_overrides:
        options.headers.update(header_overrides)
    return options


async def get_supabase_auth() -> AsyncClient:
    """Anon key client — use for ``sign_in_with_password`` and ``auth.get_user``."""
    global _auth_client
    if _auth_client is not None:
        return _auth_client

    async with _client_lock:
        if _auth_client is not None:
            return _auth_client

        settings = get_settings()
        if not settings.supabase_url or not settings.supabase_anon_key:
            raise service_unavailable("SUPABASE_URL and SUPABASE_ANON_KEY are required.")
        _auth_client = await acreate_client(
            settings.supabase_url,
            settings.supabase_anon_key,
            options=_client_options(),
        )
        return _auth_client


async def get_supabase() -> AsyncClient:
    """Service-role client — admin auth, catalog reads, profile joins (bypasses RLS)."""
    global _service_client
    if _service_client is not None:
        return _service_client

    async with _client_lock:
        if _service_client is not None:
            return _service_client

        settings = get_settings()
        if not settings.is_configured:
            raise service_unavailable(
                "Supabase is not configured. Set SUPABASE_URL and "
                "SUPABASE_SERVICE_KEY (service_role JWT)."
            )
        service = _service_role_key(settings)
        if not service:
            raise service_unavailable(
                "SUPABASE_SERVICE_KEY is missing on the server. Add the service_role JWT from "
                "Supabase → Project Settings → API → Legacy keys."
            )
        if _jwt_role(service) != "service_role":
            raise service_unavailable(
                "SUPABASE_SERVICE_KEY must be the Legacy service_role JWT (starts with eyJ…), "
                "not the anon key and not the new sb_secret_ key. Copy service_role secret from Supabase."
            )
        _service_client = await acreate_client(
            settings.supabase_url,
            service,
            options=_client_options(),
        )
        return _service_client


async def get_supabase_as_user(access_token: str) -> AsyncClient:
    """Supabase client scoped to the logged-in user (respects RLS)."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise service_unavailable("Supabase anon key is required for owner writes.")
    return await acreate_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        options=_client_options(Authorization=f"Bearer {access_token}"),
    )


async def get_supabase_for_writes(
    authorization: str | None = Header(default=None),
) -> AsyncClient:
    """DB client for inserts/updates — service_role if configured, else user JWT + RLS."""
    settings = get_settings()
    service = _service_role_key(settings)
    if service and _jwt_role(service) == "service_role":
        return await get_supabase()
    token = parse_bearer_token(authorization)
    return await get_supabase_as_user(token)
