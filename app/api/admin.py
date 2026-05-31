from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_admin
from app.core.supabase_client import get_supabase
from app.models.user import Profile

router = APIRouter(prefix="/admin", tags=["admin"])

PROFILES = "profiles"


@router.get("/owners/pending", response_model=list[Profile])
async def list_pending_owners(_: dict = Depends(require_admin)):
    """List showroom owners awaiting approval (admin only)."""
    db = await get_supabase()
    res = (
        await db.table(PROFILES)
        .select("*")
        .eq("role", "showroom_owner")
        .eq("status", "pending")
        .order("created_at", desc=True)
        .execute()
    )
    return [Profile.model_validate(row) for row in (res.data or [])]


@router.get("/owners", response_model=list[Profile])
async def list_owners(_: dict = Depends(require_admin)):
    """List all showroom owners regardless of status (admin only)."""
    db = await get_supabase()
    res = (
        await db.table(PROFILES)
        .select("*")
        .eq("role", "showroom_owner")
        .order("created_at", desc=True)
        .execute()
    )
    return [Profile.model_validate(row) for row in (res.data or [])]


@router.post("/owners/{user_id}/approve", response_model=Profile)
async def approve_owner(user_id: str, _: dict = Depends(require_admin)):
    """Approve a pending showroom owner from the admin UI (admin only)."""
    return await _set_status(user_id, "active")


@router.post("/owners/{user_id}/reject", response_model=Profile)
async def reject_owner(user_id: str, _: dict = Depends(require_admin)):
    """Reject a showroom owner request from the admin UI (admin only)."""
    return await _set_status(user_id, "rejected")


async def _set_status(user_id: str, status: str) -> Profile:
    db = await get_supabase()
    res = (
        await db.table(PROFILES)
        .update({"status": status, "confirmation_token": None})
        .eq("id", user_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Owner not found")
    return Profile.model_validate(res.data[0])
