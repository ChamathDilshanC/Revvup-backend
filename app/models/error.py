from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    """Single error payload returned to API clients."""

    code: str = Field(..., examples=["NOT_FOUND"])
    message: str = Field(..., examples=["Bike not found"])
    field: str | None = Field(default=None, examples=["email"])


class FieldError(BaseModel):
    field: str
    message: str


class ErrorResponse(BaseModel):
    """Standard error envelope for every failed API response."""

    success: bool = False
    error: ErrorBody
    errors: list[FieldError] | None = None
    request_id: str | None = None
