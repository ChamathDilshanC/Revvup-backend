from fastapi import Depends, Header, HTTPException

from app.core.config import get_settings
from app.core.supabase_client import get_supabase, get_supabase_as_user, parse_bearer_token
from app.core.supabase_http import SupabaseHTTPError


async def get_current_profile(authorization: str | None = Header(default=None)) -> dict:
    settings = get_settings()
    token = parse_bearer_token(authorization)
    auth_db = get_supabase_as_user(token)

    try:
        user = auth_db.auth_get_user(token, settings.supabase_anon_key)
    except SupabaseHTTPError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    db = get_supabase()
    rows = db.rest_select("profiles", filters={"id": f"eq.{user_id}"}, limit=1)
    if not rows:
        raise HTTPException(status_code=403, detail="Profile not found")
    return rows[0]


async def require_active_owner(profile: dict = Depends(get_current_profile)) -> dict:
    if profile.get("role") not in ("showroom_owner", "admin"):
        raise HTTPException(status_code=403, detail="Showroom owner access required")
    if profile.get("status") != "active":
        raise HTTPException(status_code=403, detail="Account is pending approval or rejected")
    return profile


async def require_admin(profile: dict = Depends(get_current_profile)) -> dict:
    if profile.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return profile
