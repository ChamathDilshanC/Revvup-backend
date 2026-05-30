from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_profile, require_active_owner
from app.core.supabase_client import get_supabase
from app.models.showroom import ShowroomDetail, ShowroomProfileUpdate, ShowroomPublic

router = APIRouter(prefix="/showrooms", tags=["showrooms"])

PROFILES = "profiles"


@router.get("", response_model=list[ShowroomPublic])
def list_showrooms():
    """Public — active showroom owners for discovery."""
    db = get_supabase()
    res = (
        db.table(PROFILES)
        .select("id, full_name, showroom_name, showroom_address, phone")
        .eq("role", "showroom_owner")
        .eq("status", "active")
        .order("showroom_name")
        .execute()
    )
    return [ShowroomPublic.model_validate(row) for row in (res.data or [])]


@router.get("/{profile_id}", response_model=ShowroomDetail)
def get_showroom(profile_id: str):
    """Public showroom profile by owner id."""
    db = get_supabase()
    res = (
        db.table(PROFILES)
        .select("id, full_name, email, showroom_name, showroom_address, phone, role, status")
        .eq("id", profile_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Showroom not found")
    row = res.data[0]
    if row.get("role") != "showroom_owner" or row.get("status") != "active":
        raise HTTPException(status_code=404, detail="Showroom not found")
    return ShowroomDetail.model_validate(row)


owner_router = APIRouter(prefix="/owner/showroom", tags=["owner — showroom profile"])


@owner_router.get("/me", response_model=ShowroomDetail)
def get_my_showroom(owner: dict = Depends(require_active_owner)):
    """Authenticated owner's showroom profile."""
    return ShowroomDetail.model_validate(owner)


@owner_router.patch("/me", response_model=ShowroomDetail)
def update_my_showroom(
    body: ShowroomProfileUpdate,
    owner: dict = Depends(require_active_owner),
):
    """Update showroom name, address, phone, or contact name."""
    db = get_supabase()
    payload = body.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")
    res = db.table(PROFILES).update(payload).eq("id", owner["id"]).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to update profile")
    return ShowroomDetail.model_validate(res.data[0])
