from pydantic import BaseModel


class BikeSummary(BaseModel):
    id: str
    name: str
    brand: str
    price: float
    image_url: str
    top_speed_mph: int | None = None


class BikeDetail(BikeSummary):
    weight_lbs: int
    engine_cc: int
    horsepower: int
    year: int
