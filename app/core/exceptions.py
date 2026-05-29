"""Application errors with stable codes for clients."""


class AppException(Exception):
    """Raise this instead of HTTPException for consistent API error bodies."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        field: str | None = None,
        errors: list[dict[str, str]] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.field = field
        self.errors = errors
        super().__init__(message)


# --- helpers (optional — keeps route code readable) -----------------------


def bad_request(message: str, *, code: str = "BAD_REQUEST", field: str | None = None) -> AppException:
    return AppException(status_code=400, code=code, message=message, field=field)


def unauthorized(message: str = "Invalid or expired credentials", *, code: str = "UNAUTHORIZED") -> AppException:
    return AppException(status_code=401, code=code, message=message)


def forbidden(message: str, *, code: str = "FORBIDDEN") -> AppException:
    return AppException(status_code=403, code=code, message=message)


def not_found(message: str = "Resource not found", *, code: str = "NOT_FOUND") -> AppException:
    return AppException(status_code=404, code=code, message=message)


def conflict(message: str, *, code: str = "CONFLICT") -> AppException:
    return AppException(status_code=409, code=code, message=message)


def service_unavailable(message: str, *, code: str = "SERVICE_UNAVAILABLE") -> AppException:
    return AppException(status_code=503, code=code, message=message)


def internal_error(message: str = "An unexpected error occurred") -> AppException:
    return AppException(status_code=500, code="INTERNAL_ERROR", message=message)
