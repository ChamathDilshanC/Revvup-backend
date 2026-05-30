from typing import Literal

from pydantic import BaseModel, EmailStr

Role = Literal["client", "showroom_owner", "admin"]
Status = Literal["active", "pending", "rejected"]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: Role = "client"
    # Required when role == "showroom_owner"
    showroom_name: str | None = None
    showroom_address: str | None = None
    phone: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Profile(BaseModel):
    id: str
    email: EmailStr
    full_name: str | None = None
    role: Role = "client"
    status: Status = "active"
    showroom_name: str | None = None
    showroom_address: str | None = None
    phone: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class ProfileUpdateRequest(BaseModel):
    """Showroom owners update shop details and map location."""

    full_name: str | None = None
    showroom_name: str | None = None
    showroom_address: str | None = None
    phone: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class AuthResponse(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    profile: Profile
    # Human-readable hint for the frontend (e.g. pending approval).
    message: str | None = None
