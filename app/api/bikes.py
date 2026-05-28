from fastapi import APIRouter, HTTPException

from app.models.bike import BikeDetail, BikeSummary

router = APIRouter(prefix="/bikes", tags=["bikes"])

MOCK_BIKES: list[BikeDetail] = [
    BikeDetail(
        id="1",
        name="Panigale V4 S",
        brand="Ducati",
        price=28995,
        image_url="https://images.unsplash.com/photo-1558981403-c5f9899a28bc?w=800",
        top_speed_mph=186,
        weight_lbs=430,
        engine_cc=1103,
        horsepower=214,
        year=2024,
    ),
    BikeDetail(
        id="2",
        name="S 1000 RR",
        brand="BMW",
        price=19995,
        image_url="https://images.unsplash.com/photo-1568772585407-9361f9bf3a87?w=800",
        top_speed_mph=186,
        weight_lbs=437,
        engine_cc=999,
        horsepower=205,
        year=2024,
    ),
    BikeDetail(
        id="3",
        name="CBR1000RR-R FIREBLADE SP",
        brand="Honda",
        price=28500,
        image_url="https://images.unsplash.com/photo-1609630875171-a86a521a48fe?w=800",
        top_speed_mph=180,
        weight_lbs=443,
        engine_cc=999,
        horsepower=214,
        year=2024,
    ),
]


@router.get("", response_model=list[BikeSummary])
def list_bikes():
    """Fetch premium bike catalog."""
    return [BikeSummary.model_validate(b) for b in MOCK_BIKES]


@router.get("/{bike_id}", response_model=BikeDetail)
def get_bike(bike_id: str):
    """Fetch structural/hardware specs: top speed, weight, engine cc, etc."""
    for bike in MOCK_BIKES:
        if bike.id == bike_id:
            return bike
    raise HTTPException(status_code=404, detail="Bike not found")
