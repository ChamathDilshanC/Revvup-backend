from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: EmailStr


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest):
    """Mock login — replace with real auth provider in production."""
    if not body.password or len(body.password) < 6:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return AuthResponse(
        access_token="mock_jwt_token_revvup",
        user_id="user_001",
        email=body.email,
    )


@router.post("/register", response_model=AuthResponse)
def register(body: RegisterRequest):
    """Mock registration — replace with database + hashed passwords."""
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    return AuthResponse(
        access_token="mock_jwt_token_revvup_new",
        user_id="user_new_001",
        email=body.email,
    )
