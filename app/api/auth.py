import uuid
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.exceptions import bad_request, conflict, forbidden, internal_error, unauthorized
from fastapi.responses import HTMLResponse

from app.core.config import get_settings
from app.core.email import build_owner_approval_email, result_page, send_email
from app.core.security import get_current_profile, require_active_owner
from app.core.supabase_client import get_supabase, get_supabase_as_user, get_supabase_auth
from app.models.user import AuthResponse, LoginRequest, Profile, ProfileUpdateRequest, RegisterRequest

router = APIRouter(prefix="/auth", tags=["auth"])

PROFILES = "profiles"


def _profile_from_row(row: dict) -> Profile:
    return Profile.model_validate(row)


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(body: RegisterRequest):
    """Register a client or a bike showroom owner.

    - **client**: account is active immediately and can log in.
    - **showroom_owner**: account is created as *pending*. An HTML approval
      email is sent to the developer; once approved the account is activated
      with admin CRUD capabilities.
    """
    if len(body.password) < 8:
        raise bad_request("Password must be at least 8 characters", field="password")

    is_owner = body.role == "showroom_owner"
    if is_owner and not body.showroom_name:
        raise bad_request("showroom_name is required for showroom owners", field="showroom_name")

    db = get_supabase()

    existing = db.table(PROFILES).select("email, role, status").eq("email", body.email).limit(1).execute()
    if existing.data:
        row = existing.data[0]
        if row.get("role") == "showroom_owner" and row.get("status") == "pending":
            raise conflict(
                "Your showroom owner application is already pending approval. "
                "Please wait for the RevvUp team to review your request. "
                "You will be able to sign in after approval.",
                code="OWNER_PENDING",
            )
        raise conflict(
            "This email is already registered. Try signing in instead.",
            code="EMAIL_EXISTS",
        )

    # Create a confirmed auth user via the admin API (service role key).
    try:
        created = db.auth.admin.create_user(
            {
                "email": body.email,
                "password": body.password,
                "email_confirm": True,
                "user_metadata": {"full_name": body.full_name, "role": body.role},
            }
        )
    except Exception:  # noqa: BLE001
        raise conflict(
            "Registration failed. This email may already be registered.",
            code="REGISTRATION_FAILED",
        )

    user = getattr(created, "user", None)
    if user is None:
        raise bad_request("Registration failed", code="REGISTRATION_FAILED")

    status = "pending" if is_owner else "active"
    token = str(uuid.uuid4()) if is_owner else None

    profile_row = {
        "id": user.id,
        "email": body.email,
        "full_name": body.full_name,
        "role": body.role,
        "status": status,
        "showroom_name": body.showroom_name,
        "showroom_address": body.showroom_address,
        "phone": body.phone,
        "confirmation_token": token,
    }

    inserted = db.table(PROFILES).insert(profile_row).execute()
    if not inserted.data:
        # Roll back the auth user so the email can be reused.
        try:
            db.auth.admin.delete_user(user.id)
        except Exception:  # noqa: BLE001
            pass
        raise internal_error("Failed to create profile")

    profile = _profile_from_row(inserted.data[0])

    if is_owner:
        _send_owner_approval_email(body, token)
        return AuthResponse(
            profile=profile,
            message=(
                "Your showroom owner application was submitted successfully and is now "
                "pending approval. We emailed the RevvUp team to review your showroom details. "
                "You cannot register again until a decision is made. Once approved, sign in "
                "with the same email and password you used here."
            ),
        )

    # Clients get a session immediately.
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

    # Load profile as the signed-in user (anon key + JWT). Does not require service_role.
    user_db = get_supabase_as_user(session["access_token"])
    res = user_db.table(PROFILES).select("*").eq("id", session["user_id"]).limit(1).execute()
    if not res.data:
        raise forbidden("Profile not found", code="PROFILE_NOT_FOUND")
    profile = _profile_from_row(res.data[0])

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
    """Return the current authenticated user's profile."""
    return _profile_from_row(profile)


@router.patch("/me", response_model=Profile)
async def update_me(body: ProfileUpdateRequest, owner: dict = Depends(require_active_owner)):
    """Update showroom profile and map pin (active showroom owners / admins)."""
    payload = body.model_dump(exclude_none=True)
    if not payload:
        raise bad_request("No fields to update")

    if body.latitude is not None and not (-90 <= body.latitude <= 90):
        raise bad_request("latitude must be between -90 and 90", field="latitude")
    if body.longitude is not None and not (-180 <= body.longitude <= 180):
        raise bad_request("longitude must be between -180 and 180", field="longitude")

    db = get_supabase()
    res = db.table(PROFILES).update(payload).eq("id", owner["id"]).execute()
    if not res.data:
        raise internal_error("Failed to update profile")
    return _profile_from_row(res.data[0])


@router.get("/confirm", response_class=HTMLResponse)
async def confirm_owner(
    token: str = Query(...),
    action: str = Query("approve", pattern="^(approve|reject)$"),
):
    """Developer-facing endpoint hit from the approval email's buttons."""
    db = get_supabase()
    res = db.table(PROFILES).select("*").eq("confirmation_token", token).limit(1).execute()
    if not res.data:
        return HTMLResponse(
            result_page(
                title="Link expired",
                message="This approval link is invalid or has already been used.",
                ok=False,
            ),
            status_code=404,
        )

    profile = res.data[0]
    new_status = "active" if action == "approve" else "rejected"

    db.table(PROFILES).update(
        {"status": new_status, "confirmation_token": None}
    ).eq("id", profile["id"]).execute()

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


# --- helpers --------------------------------------------------------------


def _sign_in(email: str, password: str) -> dict:
    # Must use anon key — service_role cannot sign in as end users.
    db = get_supabase_auth()
    try:
        result = db.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:  # noqa: BLE001
        raise unauthorized("Invalid email or password. Check your details or register first.") from exc
    if result.session is None or result.user is None:
        raise unauthorized()
    return {
        "access_token": result.session.access_token,
        "refresh_token": result.session.refresh_token,
        "user_id": result.user.id,
    }


def _send_owner_approval_email(body: RegisterRequest, token: str) -> None:
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
    send_email(
        to=settings.developer_email,
        subject=f"RevvUp — Approve showroom owner: {body.showroom_name or body.full_name}",
        html=html,
    )
