import uuid

from fastapi import APIRouter, HTTPException

from app.core.exceptions import not_found
from app.core.supabase_client import get_supabase
from app.models.bike import BikeDetail, BikeSummary

router = APIRouter(prefix="/bikes", tags=["bikes — public catalog"])

TABLE = "bikes"


def _ensure_bike_uuid(bike_id: str) -> None:
    try:
        uuid.UUID(bike_id)
    except ValueError:
        raise not_found("Bike not found")


@router.get("", response_model=list[BikeSummary])
def list_bikes():
    """Public catalog — all bikes from every showroom (Client Explore / Catalog)."""
    db = get_supabase()
    res = db.table(TABLE).select("*").order("created_at", desc=True).execute()
    return [BikeSummary.model_validate(row) for row in (res.data or [])]


@router.get("/{bike_id}", response_model=BikeDetail)
def get_bike(bike_id: str):
    """Public detail — specs: top speed, weight, engine cc, horsepower, year."""
    _ensure_bike_uuid(bike_id)
    db = get_supabase()
    res = db.table(TABLE).select("*").eq("id", bike_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Bike not found")
    return BikeDetail.model_validate(res.data[0])
