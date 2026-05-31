from fastapi import Depends, Header, HTTPException

from app.core.supabase_client import get_supabase, get_supabase_auth, parse_bearer_token


async def get_current_profile(authorization: str | None = Header(default=None)) -> dict:
    """Resolve the caller's profile from a Supabase access token.

    Expects an ``Authorization: Bearer <access_token>`` header.
    """
    token = parse_bearer_token(authorization)
    auth_db = await get_supabase_auth()

    try:
        user_res = await auth_db.auth.get_user(token)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = getattr(user_res, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    db = await get_supabase()
    res = await db.table("profiles").select("*").eq("id", user.id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=403, detail="Profile not found")
    return res.data[0]


async def require_active_owner(profile: dict = Depends(get_current_profile)) -> dict:
    """Allow only approved showroom owners (or admins) through."""
    if profile.get("role") not in ("showroom_owner", "admin"):
        raise HTTPException(status_code=403, detail="Showroom owner access required")
    if profile.get("status") != "active":
        raise HTTPException(status_code=403, detail="Account is pending approval or rejected")
    return profile


async def require_admin(profile: dict = Depends(get_current_profile)) -> dict:
    """Allow only admins through."""
    if profile.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return profile
