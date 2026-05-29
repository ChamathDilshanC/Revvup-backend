import logging
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException
from app.models.error import ErrorBody, ErrorResponse, FieldError

logger = logging.getLogger("revvup")

_STATUS_TO_CODE: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request: Request,
    field: str | None = None,
    errors: list[FieldError] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, field=field),
        errors=errors,
        request_id=_request_id(request),
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


def _code_for_status(status_code: int) -> str:
    return _STATUS_TO_CODE.get(status_code, "HTTP_ERROR")


def _message_from_http_detail(detail: object) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        first = detail[0]
        if isinstance(first, dict):
            return str(first.get("msg", first.get("message", "Request failed")))
        return str(first)
    if isinstance(detail, dict):
        return str(detail.get("message", detail.get("msg", "Request failed")))
    return "Request failed"


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    if exc.status_code >= 500:
        logger.error(
            "AppException %s: %s",
            exc.code,
            exc.message,
            extra={"request_id": _request_id(request)},
        )
    return _error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        request=request,
        field=exc.field,
        errors=[FieldError(**e) for e in exc.errors] if exc.errors else None,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Normalize FastAPI/Starlette HTTPException into the standard envelope."""
    return _error_response(
        status_code=exc.status_code,
        code=_code_for_status(exc.status_code),
        message=_message_from_http_detail(exc.detail),
        request=request,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    field_errors = [
        FieldError(
            field=".".join(str(part) for part in err.get("loc", ()) if part != "body"),
            message=str(err.get("msg", "Invalid value")),
        )
        for err in exc.errors()
    ]
    return _error_response(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Request validation failed",
        request=request,
        errors=field_errors,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all — never leak stack traces or internal messages to clients."""
    logger.exception(
        "Unhandled exception",
        extra={"request_id": _request_id(request)},
    )
    return _error_response(
        status_code=500,
        code="INTERNAL_ERROR",
        message="An unexpected error occurred. Please try again later.",
        request=request,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


async def request_id_middleware(request: Request, call_next):
    """Attach a request ID for tracing (client may send X-Request-ID)."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
