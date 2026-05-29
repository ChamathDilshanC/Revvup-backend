from pydantic import BaseModel


class BikeSummary(BaseModel):
    id: str
    name: str
    brand: str
    price: float
    image_url: str | None = None
    top_speed_mph: int | None = None


class BikeDetail(BikeSummary):
    weight_lbs: int | None = None
    engine_cc: int | None = None
    horsepower: int | None = None
    year: int | None = None


class BikeCreate(BaseModel):
    """Payload for creating a new bike (image handled separately on upload)."""

    name: str
    brand: str
    price: float
    image_url: str | None = None
    top_speed_mph: int | None = None
    weight_lbs: int | None = None
    engine_cc: int | None = None
    horsepower: int | None = None
    year: int | None = None


class BikeUpdate(BaseModel):
    """Partial update payload — every field is optional."""

    name: str | None = None
    brand: str | None = None
    price: float | None = None
    image_url: str | None = None
    top_speed_mph: int | None = None
    weight_lbs: int | None = None
    engine_cc: int | None = None
    horsepower: int | None = None
    year: int | None = None
