import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.config import get_settings
from app.core.exceptions import not_found
from app.core.security import require_active_owner
from app.core.supabase_client import get_supabase, get_supabase_for_writes
from app.core.supabase_http import SupabaseHTTPError, SupabaseRest
from app.models.bike import BikeCreate, BikeDetail, BikeSummary, BikeUpdate

router = APIRouter(prefix="/bikes", tags=["bikes"])

TABLE = "bikes"
PROFILES = "profiles"
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
logger = logging.getLogger("revvup.bikes")

_PROFILE_SELECT_WITH_MAP = (
    "id, showroom_name, showroom_address, phone, full_name, latitude, longitude"
)
_PROFILE_SELECT_BASE = "id, showroom_name, showroom_address, phone, full_name"


def _public_storage_url(settings, object_path: str) -> str:
    base = settings.supabase_url.rstrip("/")
    bucket = settings.supabase_bucket
    return f"{base}/storage/v1/object/public/{bucket}/{object_path}"


def _resolve_image_content_type(file: UploadFile) -> str:
    if file.content_type in ALLOWED_IMAGE_TYPES:
        return file.content_type
    name = (file.filename or "").lower()
    if name.endswith(".png"):
        return "image/png"
    if name.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def _ensure_bike_uuid(bike_id: str) -> None:
    try:
        uuid.UUID(bike_id)
    except ValueError:
        raise not_found("Bike not found")


def _fetch_owner_profiles(db: SupabaseRest, owner_ids: list) -> list[dict]:
    if not owner_ids:
        return []
    in_filter = f"in.({','.join(owner_ids)})"
    try:
        return db.rest_select(
            PROFILES,
            columns=_PROFILE_SELECT_WITH_MAP,
            filters={"id": in_filter},
        )
    except SupabaseHTTPError:
        logger.warning(
            "Profile map columns unavailable — run supabase_migrations/add_showroom_location.sql",
            exc_info=True,
        )
        return db.rest_select(
            PROFILES,
            columns=_PROFILE_SELECT_BASE,
            filters={"id": in_filter},
        )


def _attach_showroom_info(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    owner_ids = list({r["owner_id"] for r in rows if r.get("owner_id")})
    if not owner_ids:
        return rows

    db = get_supabase()
    profiles = _fetch_owner_profiles(db, owner_ids)
    by_id = {p["id"]: p for p in profiles}

    enriched: list[dict] = []
    for row in rows:
        item = dict(row)
        prof = by_id.get(item.get("owner_id"), {})
        item["showroom_name"] = prof.get("showroom_name") or prof.get("full_name")
        item["showroom_address"] = prof.get("showroom_address")
        item["showroom_latitude"] = prof.get("latitude")
        item["showroom_longitude"] = prof.get("longitude")
        enriched.append(item)
    return enriched


def _normalize_bike_row(row: dict) -> dict:
    item = dict(row)
    for key in ("id", "owner_id"):
        if item.get(key) is not None:
            item[key] = str(item[key])
    if item.get("price") is not None:
        item["price"] = float(item["price"])
    for key in ("top_speed_mph", "weight_lbs", "engine_cc", "horsepower", "year"):
        if item.get(key) is not None:
            item[key] = int(round(float(item[key])))
    return item


def _to_summary(row: dict) -> BikeSummary:
    return BikeSummary.model_validate(_normalize_bike_row(row))


def _to_detail(row: dict) -> BikeDetail:
    return BikeDetail.model_validate(_normalize_bike_row(row))


@router.get("", response_model=list[BikeSummary])
async def list_bikes():
    db = get_supabase()
    rows = db.rest_select(TABLE, order="created_at.desc")
    return [_to_summary(row) for row in _attach_showroom_info(rows)]


@router.get("/mine", response_model=list[BikeSummary])
async def list_my_bikes(owner: dict = Depends(require_active_owner)):
    db = get_supabase()
    filters = None if owner.get("role") == "admin" else {"owner_id": f"eq.{owner['id']}"}
    rows = db.rest_select(TABLE, filters=filters, order="created_at.desc")
    return [_to_summary(row) for row in _attach_showroom_info(rows)]


@router.get("/{bike_id}", response_model=BikeDetail)
async def get_bike(bike_id: str):
    _ensure_bike_uuid(bike_id)
    db = get_supabase()
    rows = db.rest_select(TABLE, filters={"id": f"eq.{bike_id}"}, limit=1)
    if not rows:
        raise HTTPException(status_code=404, detail="Bike not found")
    row = _attach_showroom_info(rows)[0]
    return _to_detail(row)


@router.post("", response_model=BikeDetail, status_code=201)
async def create_bike(
    body: BikeCreate,
    owner: dict = Depends(require_active_owner),
    db: SupabaseRest = Depends(get_supabase_for_writes),
):
    payload = body.model_dump(exclude_none=True)
    payload["owner_id"] = owner["id"]
    try:
        inserted = db.rest_insert(TABLE, payload)
    except SupabaseHTTPError as exc:
        logger.exception("Supabase insert bike failed")
        msg = exc.body
        if "row-level security" in msg.lower() or "42501" in msg:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Database blocked this listing (RLS). In Supabase SQL Editor, run "
                    "supabase_migrations/add_bikes_owner_rls.sql, then redeploy the backend."
                ),
            ) from exc
        raise HTTPException(status_code=500, detail=f"Failed to create bike: {msg}") from exc
    if not inserted:
        raise HTTPException(status_code=500, detail="Failed to create bike")
    try:
        row = _attach_showroom_info(inserted)[0]
        return _to_detail(row)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bike create response build failed")
        raise HTTPException(status_code=500, detail=f"Failed to create bike: {exc}") from exc


@router.patch("/{bike_id}", response_model=BikeDetail)
async def update_bike(
    bike_id: str,
    body: BikeUpdate,
    owner: dict = Depends(require_active_owner),
    db: SupabaseRest = Depends(get_supabase_for_writes),
):
    _ensure_bike_uuid(bike_id)
    payload = body.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")
    _assert_can_manage(db, bike_id, owner)
    rows = db.rest_update(TABLE, {"id": f"eq.{bike_id}"}, payload)
    if not rows:
        raise HTTPException(status_code=404, detail="Bike not found")
    return _to_detail(_attach_showroom_info(rows)[0])


@router.delete("/{bike_id}", status_code=204)
async def delete_bike(
    bike_id: str,
    owner: dict = Depends(require_active_owner),
    db: SupabaseRest = Depends(get_supabase_for_writes),
):
    _ensure_bike_uuid(bike_id)
    _assert_can_manage(db, bike_id, owner)
    db.rest_delete(TABLE, {"id": f"eq.{bike_id}"})
    return None


def _assert_can_manage(db: SupabaseRest, bike_id: str, owner: dict) -> dict:
    rows = db.rest_select(TABLE, columns="owner_id", filters={"id": f"eq.{bike_id}"}, limit=1)
    if not rows:
        raise HTTPException(status_code=404, detail="Bike not found")
    row = rows[0]
    if owner.get("role") != "admin" and row.get("owner_id") != owner["id"]:
        raise HTTPException(status_code=403, detail="You can only manage your own bikes")
    return row


@router.post("/{bike_id}/image", response_model=BikeDetail)
async def upload_bike_image(
    bike_id: str,
    file: UploadFile = File(...),
    owner: dict = Depends(require_active_owner),
    db: SupabaseRest = Depends(get_supabase_for_writes),
):
    _ensure_bike_uuid(bike_id)
    content_type = _resolve_image_content_type(file)
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_IMAGE_TYPES))}",
        )

    settings = get_settings()
    _assert_can_manage(db, bike_id, owner)

    content = await file.read()
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext in ("jpeg", "jpg", ""):
        ext = "jpg"
    elif ext not in ("png", "webp"):
        ext = "jpg"
    object_path = f"{bike_id}/{uuid.uuid4().hex}.{ext}"

    try:
        db.storage_upload(
            settings.supabase_bucket,
            object_path,
            content,
            content_type=content_type,
        )
    except SupabaseHTTPError as exc:
        logger.exception("Storage upload failed")
        raise HTTPException(status_code=500, detail=f"Image upload failed: {exc.body}") from exc

    public_url = _public_storage_url(settings, object_path)
    rows = db.rest_update(TABLE, {"id": f"eq.{bike_id}"}, {"image_url": public_url})
    if not rows:
        raise HTTPException(status_code=500, detail="Failed to attach image to bike")
    return _to_detail(_attach_showroom_info(rows)[0])
