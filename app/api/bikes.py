import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.config import get_settings
from app.core.exceptions import not_found
from app.core.security import require_active_owner
from app.core.supabase_client import get_supabase
from app.models.bike import BikeCreate, BikeDetail, BikeSummary, BikeUpdate

router = APIRouter(prefix="/bikes", tags=["bikes"])

TABLE = "bikes"
PROFILES = "profiles"
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _ensure_bike_uuid(bike_id: str) -> None:
    try:
        uuid.UUID(bike_id)
    except ValueError:
        raise not_found("Bike not found")


def _attach_showroom_info(rows: list[dict]) -> list[dict]:
    """Join owner profile showroom fields onto bike rows."""
    if not rows:
        return []
    owner_ids = list({r["owner_id"] for r in rows if r.get("owner_id")})
    if not owner_ids:
        return rows

    db = get_supabase()
    prof_res = (
        db.table(PROFILES)
        .select("id, showroom_name, showroom_address, phone, full_name")
        .in_("id", owner_ids)
        .execute()
    )
    by_id = {p["id"]: p for p in (prof_res.data or [])}

    enriched: list[dict] = []
    for row in rows:
        item = dict(row)
        prof = by_id.get(item.get("owner_id"), {})
        item["showroom_name"] = prof.get("showroom_name") or prof.get("full_name")
        item["showroom_address"] = prof.get("showroom_address")
        enriched.append(item)
    return enriched


def _to_summary(row: dict) -> BikeSummary:
    return BikeSummary.model_validate(row)


def _to_detail(row: dict) -> BikeDetail:
    return BikeDetail.model_validate(row)


@router.get("", response_model=list[BikeSummary])
def list_bikes():
    """Public catalog — all bikes with showroom info for client Explore."""
    db = get_supabase()
    res = db.table(TABLE).select("*").order("created_at", desc=True).execute()
    rows = _attach_showroom_info(res.data or [])
    return [_to_summary(row) for row in rows]


@router.get("/mine", response_model=list[BikeSummary])
def list_my_bikes(owner: dict = Depends(require_active_owner)):
    """Bikes the logged-in showroom owner (or all bikes for admin) can manage."""
    db = get_supabase()
    query = db.table(TABLE).select("*").order("created_at", desc=True)
    if owner.get("role") != "admin":
        query = query.eq("owner_id", owner["id"])
    res = query.execute()
    rows = _attach_showroom_info(res.data or [])
    return [_to_summary(row) for row in rows]


@router.get("/{bike_id}", response_model=BikeDetail)
def get_bike(bike_id: str):
    """Full bike specs plus showroom info."""
    _ensure_bike_uuid(bike_id)
    db = get_supabase()
    res = db.table(TABLE).select("*").eq("id", bike_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Bike not found")
    row = _attach_showroom_info(res.data)[0]
    return _to_detail(row)


@router.post("", response_model=BikeDetail, status_code=201)
def create_bike(body: BikeCreate, owner: dict = Depends(require_active_owner)):
    """Insert a new bike (active showroom owner / admin)."""
    db = get_supabase()
    payload = body.model_dump(exclude_none=True)
    payload["owner_id"] = owner["id"]
    res = db.table(TABLE).insert(payload).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to create bike")
    row = _attach_showroom_info(res.data)[0]
    return _to_detail(row)


@router.patch("/{bike_id}", response_model=BikeDetail)
def update_bike(bike_id: str, body: BikeUpdate, owner: dict = Depends(require_active_owner)):
    """Partially update a bike (owner of the bike, or admin)."""
    _ensure_bike_uuid(bike_id)
    db = get_supabase()
    payload = body.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")
    _assert_can_manage(db, bike_id, owner)
    res = db.table(TABLE).update(payload).eq("id", bike_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Bike not found")
    row = _attach_showroom_info(res.data)[0]
    return _to_detail(row)


@router.delete("/{bike_id}", status_code=204)
def delete_bike(bike_id: str, owner: dict = Depends(require_active_owner)):
    """Delete a bike (owner of the bike, or admin)."""
    _ensure_bike_uuid(bike_id)
    db = get_supabase()
    _assert_can_manage(db, bike_id, owner)
    db.table(TABLE).delete().eq("id", bike_id).execute()
    return None


def _assert_can_manage(db, bike_id: str, owner: dict) -> dict:
    """Ensure the caller owns the bike (admins bypass this check)."""
    res = db.table(TABLE).select("owner_id").eq("id", bike_id).limit(1).execute()
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
):
    """Upload an image to Supabase Storage and attach its public URL to the bike."""
    _ensure_bike_uuid(bike_id)
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_IMAGE_TYPES))}",
        )

    db = get_supabase()
    settings = get_settings()

    _assert_can_manage(db, bike_id, owner)

    content = await file.read()
    extension = (file.filename or "").rsplit(".", 1)[-1].lower() or "jpg"
    object_path = f"{bike_id}/{uuid.uuid4().hex}.{extension}"

    storage = db.storage.from_(settings.supabase_bucket)
    try:
        storage.upload(
            path=object_path,
            file=content,
            file_options={"content-type": file.content_type, "upsert": "true"},
        )
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Image upload failed")

    public_url = storage.get_public_url(object_path)

    res = db.table(TABLE).update({"image_url": public_url}).eq("id", bike_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to attach image to bike")
    row = _attach_showroom_info(res.data)[0]
    return _to_detail(row)
