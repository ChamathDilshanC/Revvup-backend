from pydantic import BaseModel


class ShowroomPublic(BaseModel):
    id: str
    full_name: str | None = None
    showroom_name: str | None = None
    showroom_address: str | None = None
    phone: str | None = None


class ShowroomDetail(ShowroomPublic):
    email: str | None = None


class ShowroomProfileUpdate(BaseModel):
    full_name: str | None = None
    showroom_name: str | None = None
    showroom_address: str | None = None
    phone: str | None = None
