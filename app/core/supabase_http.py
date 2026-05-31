"""Supabase REST/Auth client via stdlib urllib (reliable on Vercel serverless).

The supabase-py SDK uses httpx/httpcore, which fails on Vercel Python 3.12 with
``ConnectError: [Errno 16] Device or resource busy`` during DNS/TCP connect.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import service_unavailable


class SupabaseHTTPError(Exception):
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body
        super().__init__(f"Supabase HTTP {status}: {body[:300]}")


def jwt_role(key: str) -> str | None:
    import base64

    try:
        payload = key.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        return data.get("role")
    except Exception:  # noqa: BLE001
        return None


def _service_role_key(settings) -> str:
    import os

    return (
        settings.supabase_service_key.strip()
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    )


def _request(
    *,
    method: str,
    url: str,
    api_key: str,
    bearer: str,
    body: Any | None = None,
    extra_headers: dict[str, str] | None = None,
    raw_body: bytes | None = None,
    timeout: float = 30.0,
) -> Any:
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {bearer}",
    }
    if extra_headers:
        headers.update(extra_headers)

    payload: bytes | None = raw_body
    if body is not None and raw_body is None:
        headers.setdefault("Content-Type", "application/json")
        payload = json.dumps(body).encode()

    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode()
            if not raw:
                return None
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise SupabaseHTTPError(exc.code, detail) from exc
    except urllib.error.URLError as exc:
        raise service_unavailable(f"Cannot reach Supabase: {exc.reason}") from exc


class SupabaseRest:
    """Minimal PostgREST + Auth wrapper for RevvUp backend routes."""

    def __init__(self, *, api_key: str, bearer: str | None = None) -> None:
        settings = get_settings()
        if not settings.supabase_url:
            raise service_unavailable("SUPABASE_URL is not configured.")
        self.base = settings.supabase_url.rstrip("/")
        self.api_key = api_key
        self.bearer = bearer or api_key

    def _rest_url(self, table: str, params: dict[str, str]) -> str:
        query = urllib.parse.urlencode(params)
        return f"{self.base}/rest/v1/{table}?{query}"

    def rest_select(
        self,
        table: str,
        *,
        columns: str = "*",
        filters: dict[str, str] | None = None,
        order: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        params: dict[str, str] = {"select": columns}
        if filters:
            params.update(filters)
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = str(limit)
        url = self._rest_url(table, params)
        result = _request(
            method="GET",
            url=url,
            api_key=self.api_key,
            bearer=self.bearer,
        )
        return result or []

    def rest_insert(self, table: str, row: dict) -> list[dict]:
        url = f"{self.base}/rest/v1/{table}"
        result = _request(
            method="POST",
            url=url,
            api_key=self.api_key,
            bearer=self.bearer,
            body=row,
            extra_headers={"Prefer": "return=representation"},
        )
        return result or []

    def rest_update(self, table: str, filters: dict[str, str], payload: dict) -> list[dict]:
        url = self._rest_url(table, filters)
        result = _request(
            method="PATCH",
            url=url,
            api_key=self.api_key,
            bearer=self.bearer,
            body=payload,
            extra_headers={"Prefer": "return=representation"},
        )
        return result or []

    def rest_delete(self, table: str, filters: dict[str, str]) -> None:
        url = self._rest_url(table, filters)
        _request(
            method="DELETE",
            url=url,
            api_key=self.api_key,
            bearer=self.bearer,
        )

    def auth_admin_create_user(self, attrs: dict) -> dict:
        url = f"{self.base}/auth/v1/admin/users"
        return _request(
            method="POST",
            url=url,
            api_key=self.api_key,
            bearer=self.bearer,
            body=attrs,
        )

    def auth_admin_delete_user(self, user_id: str) -> None:
        url = f"{self.base}/auth/v1/admin/users/{urllib.parse.quote(user_id, safe='')}"
        _request(
            method="DELETE",
            url=url,
            api_key=self.api_key,
            bearer=self.bearer,
        )

    def auth_sign_in(self, email: str, password: str, anon_key: str) -> dict:
        url = f"{self.base}/auth/v1/token?grant_type=password"
        return _request(
            method="POST",
            url=url,
            api_key=anon_key,
            bearer=anon_key,
            body={"email": email, "password": password},
        )

    def auth_get_user(self, access_token: str, anon_key: str) -> dict:
        url = f"{self.base}/auth/v1/user"
        return _request(
            method="GET",
            url=url,
            api_key=anon_key,
            bearer=access_token,
        )

    def storage_upload(
        self,
        bucket: str,
        path: str,
        content: bytes,
        *,
        content_type: str,
    ) -> None:
        encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
        url = f"{self.base}/storage/v1/object/{bucket}/{encoded_path}"
        _request(
            method="POST",
            url=url,
            api_key=self.api_key,
            bearer=self.bearer,
            raw_body=content,
            extra_headers={
                "Content-Type": content_type,
                "x-upsert": "true",
            },
        )


def get_service_client() -> SupabaseRest:
    settings = get_settings()
    service = _service_role_key(settings)
    if not service:
        raise service_unavailable("SUPABASE_SERVICE_KEY is missing on the server.")
    return SupabaseRest(api_key=service, bearer=service)


def get_user_client(access_token: str) -> SupabaseRest:
    settings = get_settings()
    if not settings.supabase_anon_key:
        raise service_unavailable("SUPABASE_ANON_KEY is required.")
    return SupabaseRest(api_key=settings.supabase_anon_key, bearer=access_token)


def get_anon_client() -> SupabaseRest:
    settings = get_settings()
    if not settings.supabase_anon_key:
        raise service_unavailable("SUPABASE_ANON_KEY is required.")
    key = settings.supabase_anon_key
    return SupabaseRest(api_key=key, bearer=key)
