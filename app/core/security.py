from fastapi import Depends, Header, HTTPException

from app.core.supabase_client import get_supabase


def get_current_profile(authorization: str | None = Header(default=None)) -> dict:
    """Resolve the caller's profile from a Supabase access token.

    Expects an ``Authorization: Bearer <access_token>`` header.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1].strip()
    db = get_supabase()

    try:
        user_res = db.auth.get_user(token)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = getattr(user_res, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    res = db.table("profiles").select("*").eq("id", user.id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=403, detail="Profile not found")
    return res.data[0]


def require_active_owner(profile: dict = Depends(get_current_profile)) -> dict:
    """Allow only approved showroom owners (or admins) through."""
    if profile.get("role") not in ("showroom_owner", "admin"):
        raise HTTPException(status_code=403, detail="Showroom owner access required")
    if profile.get("status") != "active":
        raise HTTPException(status_code=403, detail="Account is pending approval or rejected")
    return profile


def require_admin(profile: dict = Depends(get_current_profile)) -> dict:
    """Allow only admins through."""
    if profile.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return profile
