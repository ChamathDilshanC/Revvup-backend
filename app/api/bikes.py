import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from supabase import AsyncClient

from app.core.config import get_settings
from app.core.exceptions import not_found
from app.core.security import require_active_owner
from app.core.supabase_client import get_supabase, get_supabase_for_writes
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
    """Stable public URL for a file in the bike-images bucket."""
    base = settings.supabase_url.rstrip("/")
    bucket = settings.supabase_bucket
    return f"{base}/storage/v1/object/public/{bucket}/{object_path}"


def _resolve_image_content_type(file: UploadFile) -> str:
    """React Native uploads often omit content_type — infer from filename."""
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


async def _fetch_owner_profiles(db: AsyncClient, owner_ids: list) -> list[dict]:
    """Load owner profiles; fall back if map columns are not migrated yet."""
    try:
        res = (
            await db.table(PROFILES)
            .select(_PROFILE_SELECT_WITH_MAP)
            .in_("id", owner_ids)
            .execute()
        )
        return res.data or []
    except Exception:  # noqa: BLE001
        logger.warning(
            "Profile map columns unavailable — run supabase_migrations/add_showroom_location.sql",
            exc_info=True,
        )
        res = (
            await db.table(PROFILES)
            .select(_PROFILE_SELECT_BASE)
            .in_("id", owner_ids)
            .execute()
        )
        return res.data or []


async def _attach_showroom_info(rows: list[dict]) -> list[dict]:
    """Join owner profile showroom fields onto bike rows."""
    if not rows:
        return []
    owner_ids = list({r["owner_id"] for r in rows if r.get("owner_id")})
    if not owner_ids:
        return rows

    db = await get_supabase()
    profiles = await _fetch_owner_profiles(db, owner_ids)
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
    """Coerce Supabase JSON types for Pydantic response models."""
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
    """Public catalog — all bikes with showroom info for client Explore."""
    db = await get_supabase()
    res = await db.table(TABLE).select("*").order("created_at", desc=True).execute()
    rows = await _attach_showroom_info(res.data or [])
    return [_to_summary(row) for row in rows]


@router.get("/mine", response_model=list[BikeSummary])
async def list_my_bikes(owner: dict = Depends(require_active_owner)):
    """Bikes the logged-in showroom owner (or all bikes for admin) can manage."""
    db = await get_supabase()
    query = db.table(TABLE).select("*").order("created_at", desc=True)
    if owner.get("role") != "admin":
        query = query.eq("owner_id", owner["id"])
    res = await query.execute()
    rows = await _attach_showroom_info(res.data or [])
    return [_to_summary(row) for row in rows]


@router.get("/{bike_id}", response_model=BikeDetail)
async def get_bike(bike_id: str):
    """Full bike specs plus showroom info."""
    _ensure_bike_uuid(bike_id)
    db = await get_supabase()
    res = await db.table(TABLE).select("*").eq("id", bike_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Bike not found")
    row = (await _attach_showroom_info(res.data))[0]
    return _to_detail(row)


@router.post("", response_model=BikeDetail, status_code=201)
async def create_bike(
    body: BikeCreate,
    owner: dict = Depends(require_active_owner),
    db: AsyncClient = Depends(get_supabase_for_writes),
):
    """Insert a new bike (active showroom owner / admin)."""
    payload = body.model_dump(exclude_none=True)
    payload["owner_id"] = owner["id"]
    try:
        res = await db.table(TABLE).insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Supabase insert bike failed")
        msg = str(exc)
        if "row-level security" in msg.lower() or "42501" in msg:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Database blocked this listing (RLS). In Supabase SQL Editor, run "
                    "supabase_migrations/add_bikes_owner_rls.sql, then redeploy the backend."
                ),
            ) from exc
        raise HTTPException(status_code=500, detail=f"Failed to create bike: {exc}") from exc
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to create bike")
    try:
        row = (await _attach_showroom_info(res.data))[0]
        return _to_detail(row)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Bike create response build failed")
        raise HTTPException(status_code=500, detail=f"Failed to create bike: {exc}") from exc


@router.patch("/{bike_id}", response_model=BikeDetail)
async def update_bike(
    bike_id: str,
    body: BikeUpdate,
    owner: dict = Depends(require_active_owner),
    db: AsyncClient = Depends(get_supabase_for_writes),
):
    """Partially update a bike (owner of the bike, or admin)."""
    _ensure_bike_uuid(bike_id)
    payload = body.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")
    await _assert_can_manage(db, bike_id, owner)
    res = await db.table(TABLE).update(payload).eq("id", bike_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Bike not found")
    row = (await _attach_showroom_info(res.data))[0]
    return _to_detail(row)


@router.delete("/{bike_id}", status_code=204)
async def delete_bike(
    bike_id: str,
    owner: dict = Depends(require_active_owner),
    db: AsyncClient = Depends(get_supabase_for_writes),
):
    """Delete a bike (owner of the bike, or admin)."""
    _ensure_bike_uuid(bike_id)
    await _assert_can_manage(db, bike_id, owner)
    await db.table(TABLE).delete().eq("id", bike_id).execute()
    return None


async def _assert_can_manage(db: AsyncClient, bike_id: str, owner: dict) -> dict:
    """Ensure the caller owns the bike (admins bypass this check)."""
    res = await db.table(TABLE).select("owner_id").eq("id", bike_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Bike not found")
    row = res.data[0]
    if owner.get("role") != "admin" and row.get("owner_id") != owner["id"]:
        raise HTTPException(status_code=403, detail="You can only manage your own bikes")
    return row


@router.post("/{bike_id}/image", response_model=BikeDetail)
async def upload_bike_image(
    bike_id: str,
    file: UploadFile = File(...),
    owner: dict = Depends(require_active_owner),
    db: AsyncClient = Depends(get_supabase_for_writes),
):
    """Upload an image to Supabase Storage and attach its public URL to the bike."""
    _ensure_bike_uuid(bike_id)
    content_type = _resolve_image_content_type(file)
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_IMAGE_TYPES))}",
        )

    settings = get_settings()

    await _assert_can_manage(db, bike_id, owner)

    content = await file.read()
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext in ("jpeg", "jpg", ""):
        ext = "jpg"
    elif ext not in ("png", "webp"):
        ext = "jpg"
    object_path = f"{bike_id}/{uuid.uuid4().hex}.{ext}"

    storage = db.storage.from_(settings.supabase_bucket)
    try:
        await storage.upload(
            path=object_path,
            file=content,
            file_options={"content-type": content_type, "upsert": "true"},
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Storage upload failed")
        raise HTTPException(status_code=500, detail=f"Image upload failed: {exc}") from exc

    public_url = _public_storage_url(settings, object_path)

    res = await db.table(TABLE).update({"image_url": public_url}).eq("id", bike_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to attach image to bike")
    row = (await _attach_showroom_info(res.data))[0]
    return _to_detail(row)
