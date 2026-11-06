import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.context import get_current_context

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Standard application exception translating to unified HTTP responses."""

    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        error_code: str = "BAD_REQUEST",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.detail = detail
        self.status_code = status_code
        self.error_code = error_code
        self.headers = headers
        super().__init__(detail)

    @classmethod
    def bad_request(cls, detail: str) -> "AppException":
        return cls(detail, status.HTTP_400_BAD_REQUEST, "BAD_REQUEST")

    @classmethod
    def unauthorized(
        cls,
        detail: str = "Authentication required",
        error_code: str = "UNAUTHORIZED",
    ) -> "AppException":
        return cls(
            detail,
            status.HTTP_401_UNAUTHORIZED,
            error_code,
            headers={"WWW-Authenticate": "Bearer"},
        )

    @classmethod
    def forbidden(cls, detail: str = "Access denied") -> "AppException":
        return cls(detail, status.HTTP_403_FORBIDDEN, "FORBIDDEN")

    @classmethod
    def not_found(cls, resource: str = "Resource") -> "AppException":
        return cls(f"{resource} not found", status.HTTP_404_NOT_FOUND, "NOT_FOUND")

    @classmethod
    def conflict(cls, detail: str) -> "AppException":
        return cls(detail, status.HTTP_409_CONFLICT, "CONFLICT")

    @classmethod
    def locked(cls, detail: str = "Account is temporarily locked", retry_after: int = 60) -> "AppException":
        return cls(
            detail,
            status.HTTP_423_LOCKED,
            "ACCOUNT_LOCKED",
            headers={"Retry-After": str(retry_after)},
        )


def _build_error_response(
    detail: str,
    error_code: str,
    status_code: int,
    errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ctx = get_current_context()
    payload: dict[str, Any] = {
        "detail": detail,
        "error_code": error_code,
        "status_code": status_code,
        "request_id": ctx.request_id if ctx else None,
    }
    if errors is not None:
        payload["errors"] = errors
    return payload


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_build_error_response(exc.detail, exc.error_code, exc.status_code),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]} for err in exc.errors()]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_build_error_response("Validation error", "VALIDATION_ERROR", 422, errors),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_build_error_response(str(exc.detail), "HTTP_ERROR", exc.status_code),
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unexpected error occurred: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_build_error_response("Internal server error", "INTERNAL_ERROR", 500),
        )
