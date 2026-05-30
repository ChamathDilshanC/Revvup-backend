import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.config import get_settings
from app.core.exceptions import not_found
from app.core.security import require_active_owner
from app.core.supabase_client import get_supabase
from app.models.bike import BikeCreate, BikeDetail, BikeSummary, BikeUpdate

router = APIRouter(prefix="/owner/bikes", tags=["owner — showroom inventory"])

TABLE = "bikes"
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _ensure_bike_uuid(bike_id: str) -> None:
    try:
        uuid.UUID(bike_id)
    except ValueError:
        raise not_found("Bike not found")


def _assert_owns_bike(db, bike_id: str, owner: dict) -> dict:
    res = db.table(TABLE).select("owner_id").eq("id", bike_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Bike not found")
    row = res.data[0]
    if owner.get("role") != "admin" and row.get("owner_id") != owner["id"]:
        raise HTTPException(status_code=403, detail="You can only manage bikes in your showroom")
    return row


@router.get("", response_model=list[BikeSummary])
def list_owner_bikes(owner: dict = Depends(require_active_owner)):
    """Owner dashboard — only this showroom's listings."""
    db = get_supabase()
    query = db.table(TABLE).select("*").order("created_at", desc=True)
    if owner.get("role") != "admin":
        query = query.eq("owner_id", owner["id"])
    res = query.execute()
    return [BikeSummary.model_validate(row) for row in (res.data or [])]


@router.post("", response_model=BikeDetail, status_code=201)
def create_owner_bike(body: BikeCreate, owner: dict = Depends(require_active_owner)):
    """Add a bike to the authenticated owner's showroom."""
    db = get_supabase()
    payload = body.model_dump(exclude_none=True)
    payload["owner_id"] = owner["id"]
    res = db.table(TABLE).insert(payload).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to create bike")
    return BikeDetail.model_validate(res.data[0])


@router.put("/{bike_id}", response_model=BikeDetail)
@router.patch("/{bike_id}", response_model=BikeDetail)
def update_owner_bike(
    bike_id: str,
    body: BikeUpdate,
    owner: dict = Depends(require_active_owner),
):
    """Update a bike that belongs to this showroom."""
    _ensure_bike_uuid(bike_id)
    db = get_supabase()
    payload = body.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")
    _assert_owns_bike(db, bike_id, owner)
    res = db.table(TABLE).update(payload).eq("id", bike_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Bike not found")
    return BikeDetail.model_validate(res.data[0])


@router.delete("/{bike_id}", status_code=204)
def delete_owner_bike(bike_id: str, owner: dict = Depends(require_active_owner)):
    """Remove a bike from this showroom."""
    _ensure_bike_uuid(bike_id)
    db = get_supabase()
    _assert_owns_bike(db, bike_id, owner)
    db.table(TABLE).delete().eq("id", bike_id).execute()
    return None


@router.post("/{bike_id}/image", response_model=BikeDetail)
async def upload_owner_bike_image(
    bike_id: str,
    file: UploadFile = File(...),
    owner: dict = Depends(require_active_owner),
):
    """Upload image to Supabase Storage and attach URL to owner's bike."""
    _ensure_bike_uuid(bike_id)
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_IMAGE_TYPES))}",
        )

    db = get_supabase()
    settings = get_settings()
    _assert_owns_bike(db, bike_id, owner)

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
    return BikeDetail.model_validate(res.data[0])
