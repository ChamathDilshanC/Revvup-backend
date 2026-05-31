from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_admin
from app.core.supabase_client import get_supabase
from app.models.user import Profile

router = APIRouter(prefix="/admin", tags=["admin"])

PROFILES = "profiles"


@router.get("/owners/pending", response_model=list[Profile])
async def list_pending_owners(_: dict = Depends(require_admin)):
    db = get_supabase()
    rows = db.rest_select(
        PROFILES,
        filters={"role": "eq.showroom_owner", "status": "eq.pending"},
        order="created_at.desc",
    )
    return [Profile.model_validate(row) for row in rows]


@router.get("/owners", response_model=list[Profile])
async def list_owners(_: dict = Depends(require_admin)):
    db = get_supabase()
    rows = db.rest_select(
        PROFILES,
        filters={"role": "eq.showroom_owner"},
        order="created_at.desc",
    )
    return [Profile.model_validate(row) for row in rows]


@router.post("/owners/{user_id}/approve", response_model=Profile)
async def approve_owner(user_id: str, _: dict = Depends(require_admin)):
    return _set_status(user_id, "active")


@router.post("/owners/{user_id}/reject", response_model=Profile)
async def reject_owner(user_id: str, _: dict = Depends(require_admin)):
    return _set_status(user_id, "rejected")


def _set_status(user_id: str, status: str) -> Profile:
    db = get_supabase()
    rows = db.rest_update(
        PROFILES,
        {"id": f"eq.{user_id}"},
        {"status": status, "confirmation_token": None},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Owner not found")
    return Profile.model_validate(rows[0])
