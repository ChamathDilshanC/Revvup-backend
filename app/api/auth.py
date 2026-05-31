import logging
import uuid
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.core.config import get_settings
from app.core.email import build_owner_approval_email, result_page, send_email
from app.core.exceptions import bad_request, conflict, forbidden, internal_error, unauthorized
from app.core.security import get_current_profile, require_active_owner
from app.core.supabase_client import get_supabase, get_supabase_as_user, get_supabase_auth
from app.core.supabase_http import SupabaseHTTPError
from app.models.user import AuthResponse, LoginRequest, Profile, ProfileUpdateRequest, RegisterRequest

router = APIRouter(prefix="/auth", tags=["auth"])

PROFILES = "profiles"
logger = logging.getLogger("revvup.auth")


def _profile_from_row(row: dict) -> Profile:
    return Profile.model_validate(row)


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(body: RegisterRequest):
    """Register a client or a bike showroom owner."""
    if len(body.password) < 8:
        raise bad_request("Password must be at least 8 characters", field="password")

    is_owner = body.role == "showroom_owner"
    if is_owner and not body.showroom_name:
        raise bad_request("showroom_name is required for showroom owners", field="showroom_name")

    db = get_supabase()

    try:
        created = db.auth_admin_create_user(
            {
                "email": body.email,
                "password": body.password,
                "email_confirm": True,
                "user_metadata": {"full_name": body.full_name, "role": body.role},
            }
        )
    except SupabaseHTTPError:
        raise conflict(
            "Registration failed. This email may already be registered.",
            code="REGISTRATION_FAILED",
        )

    user_id = created.get("id")
    if not user_id:
        raise bad_request("Registration failed", code="REGISTRATION_FAILED")

    status = "pending" if is_owner else "active"
    token = str(uuid.uuid4()) if is_owner else None

    profile_row = {
        "id": user_id,
        "email": body.email,
        "full_name": body.full_name,
        "role": body.role,
        "status": status,
        "showroom_name": body.showroom_name,
        "showroom_address": body.showroom_address,
        "phone": body.phone,
        "confirmation_token": token,
    }

    try:
        inserted = db.rest_insert(PROFILES, profile_row)
    except SupabaseHTTPError:
        try:
            db.auth_admin_delete_user(user_id)
        except SupabaseHTTPError:
            pass
        raise internal_error("Failed to create profile")

    if not inserted:
        try:
            db.auth_admin_delete_user(user_id)
        except SupabaseHTTPError:
            pass
        raise internal_error("Failed to create profile")

    profile = _profile_from_row(inserted[0])

    if is_owner:
        email_sent, approve_url = _send_owner_approval_email(body, token)
        if not email_sent:
            logger.warning(
                "Approval email not sent for %s. Manual approve: %s",
                body.email,
                approve_url,
            )
        email_note = (
            "We emailed the RevvUp team to review your showroom details."
            if email_sent
            else "Your application is saved and pending manual review by the RevvUp team."
        )
        return AuthResponse(
            profile=profile,
            message=(
                "Your showroom owner application was submitted successfully and is now "
                f"pending approval. {email_note} "
                "Once approved, sign in with the same email and password you used here."
            ),
        )

    session = _sign_in(body.email, body.password)
    return AuthResponse(
        access_token=session["access_token"],
        refresh_token=session["refresh_token"],
        profile=profile,
        message="Welcome to RevvUp!",
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    """Authenticate via Supabase Auth and return the profile + role."""
    session = _sign_in(body.email, body.password)

    user_db = get_supabase_as_user(session["access_token"])
    rows = user_db.rest_select(
        PROFILES,
        filters={"id": f"eq.{session['user_id']}"},
        limit=1,
    )
    if not rows:
        raise forbidden("Profile not found", code="PROFILE_NOT_FOUND")
    profile = _profile_from_row(rows[0])

    if profile.status == "pending":
        raise forbidden("Account is pending approval", code="ACCOUNT_PENDING")
    if profile.status == "rejected":
        raise forbidden("Account request was rejected", code="ACCOUNT_REJECTED")

    return AuthResponse(
        access_token=session["access_token"],
        refresh_token=session["refresh_token"],
        profile=profile,
    )


@router.get("/me", response_model=Profile)
async def me(profile: dict = Depends(get_current_profile)):
    return _profile_from_row(profile)


@router.patch("/me", response_model=Profile)
async def update_me(body: ProfileUpdateRequest, owner: dict = Depends(require_active_owner)):
    payload = body.model_dump(exclude_none=True)
    if not payload:
        raise bad_request("No fields to update")

    if body.latitude is not None and not (-90 <= body.latitude <= 90):
        raise bad_request("latitude must be between -90 and 90", field="latitude")
    if body.longitude is not None and not (-180 <= body.longitude <= 180):
        raise bad_request("longitude must be between -180 and 180", field="longitude")

    db = get_supabase()
    rows = db.rest_update(PROFILES, {"id": f"eq.{owner['id']}"}, payload)
    if not rows:
        raise internal_error("Failed to update profile")
    return _profile_from_row(rows[0])


@router.get("/confirm", response_class=HTMLResponse)
async def confirm_owner(
    token: str = Query(...),
    action: str = Query("approve", pattern="^(approve|reject)$"),
):
    db = get_supabase()
    rows = db.rest_select(
        PROFILES,
        filters={"confirmation_token": f"eq.{token}"},
        limit=1,
    )
    if not rows:
        return HTMLResponse(
            result_page(
                title="Link expired",
                message="This approval link is invalid or has already been used.",
                ok=False,
            ),
            status_code=404,
        )

    profile = rows[0]
    new_status = "active" if action == "approve" else "rejected"

    db.rest_update(
        PROFILES,
        {"id": f"eq.{profile['id']}"},
        {"status": new_status, "confirmation_token": None},
    )

    if action == "approve":
        return HTMLResponse(
            result_page(
                title="Showroom owner approved",
                message=f"{profile.get('full_name') or profile['email']} can now log in with admin capabilities.",
                ok=True,
            )
        )
    return HTMLResponse(
        result_page(
            title="Request rejected",
            message=f"The request from {profile.get('full_name') or profile['email']} has been rejected.",
            ok=False,
        )
    )


def _sign_in(email: str, password: str) -> dict:
    settings = get_settings()
    db = get_supabase_auth()
    try:
        result = db.auth_sign_in(email, password, settings.supabase_anon_key)
    except SupabaseHTTPError as exc:
        raise unauthorized("Invalid email or password. Check your details or register first.") from exc
    user = result.get("user") or {}
    if not result.get("access_token") or not user.get("id"):
        raise unauthorized()
    return {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token", ""),
        "user_id": user["id"],
    }


def _send_owner_approval_email(body: RegisterRequest, token: str) -> tuple[bool, str]:
    settings = get_settings()
    base = settings.effective_app_base_url
    approve_url = f"{base}/api/v1/auth/confirm?{urlencode({'token': token, 'action': 'approve'})}"
    reject_url = f"{base}/api/v1/auth/confirm?{urlencode({'token': token, 'action': 'reject'})}"

    html = build_owner_approval_email(
        full_name=body.full_name,
        email=body.email,
        showroom_name=body.showroom_name,
        showroom_address=body.showroom_address,
        phone=body.phone,
        approve_url=approve_url,
        reject_url=reject_url,
    )
    sent = send_email(
        to=settings.developer_email,
        subject=f"RevvUp — Approve showroom owner: {body.showroom_name or body.full_name}",
        html=html,
    )
    return sent, approve_url
