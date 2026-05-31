from fastapi import APIRouter, Depends, HTTPException

from app.core.config import get_settings
from app.core.email import build_owner_approval_email, send_email
from app.core.security import require_admin
from app.core.supabase_client import get_supabase
from app.models.user import Profile, RegisterRequest

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


@router.post("/owners/{user_id}/notify", status_code=204)
async def resend_owner_approval_email(user_id: str, _: dict = Depends(require_admin)):
    """Resend the HTML approval email for a pending showroom owner."""
    db = get_supabase()
    rows = db.rest_select(
        PROFILES,
        filters={"id": f"eq.{user_id}", "role": "eq.showroom_owner", "status": "eq.pending"},
        limit=1,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Pending owner not found")

    profile = rows[0]
    token = profile.get("confirmation_token")
    if not token:
        raise HTTPException(status_code=400, detail="No confirmation token on this profile")

    settings = get_settings()
    from urllib.parse import urlencode

    base = settings.effective_app_base_url
    approve_url = f"{base}/api/v1/auth/confirm?{urlencode({'token': token, 'action': 'approve'})}"
    reject_url = f"{base}/api/v1/auth/confirm?{urlencode({'token': token, 'action': 'reject'})}"

    body = RegisterRequest(
        email=profile["email"],
        password="unused",
        full_name=profile.get("full_name") or profile["email"],
        role="showroom_owner",
        showroom_name=profile.get("showroom_name"),
        showroom_address=profile.get("showroom_address"),
        phone=profile.get("phone"),
    )
    html = build_owner_approval_email(
        full_name=body.full_name,
        email=body.email,
        showroom_name=body.showroom_name,
        showroom_address=body.showroom_address,
        phone=body.phone,
        approve_url=approve_url,
        reject_url=reject_url,
    )
    if not send_email(
        to=settings.developer_email,
        subject=f"RevvUp — Approve showroom owner: {body.showroom_name or body.full_name}",
        html=html,
    ):
        raise HTTPException(status_code=502, detail="Failed to send approval email")
    return None
