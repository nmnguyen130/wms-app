import re
import time
import uuid

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings
from app.core.context import RequestContext, bind_context

_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9._-]{1,64}")
_SECURITY_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
)
_HSTS_HEADER = (b"strict-transport-security", b"max-age=63072000; includeSubDomains; preload")


class RequestContextMiddleware:
    """ASGI middleware for correlation IDs, timing, and security headers."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.perf_counter()
        headers = dict(scope.get("headers", []))

        raw_request_id = headers.get(b"x-request-id", b"").decode("latin-1")
        request_id = raw_request_id if _REQUEST_ID_RE.fullmatch(raw_request_id) else str(uuid.uuid4())

        client = scope.get("client")
        ctx = RequestContext(
            request_id=request_id,
            client_ip=client[0] if client else "127.0.0.1",
        )

        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > settings.MAX_REQUEST_BODY_BYTES:
                    response = JSONResponse(
                        status_code=413,
                        content={
                            "detail": "Request payload too large",
                            "error_code": "PAYLOAD_TOO_LARGE",
                            "status_code": 413,
                            "request_id": request_id,
                        },
                        headers={"x-request-id": request_id},
                    )
                    await response(scope, receive, send)
                    return
            except ValueError:
                pass

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                response_headers = list(message.get("headers", []))
                response_headers.append((b"x-request-id", request_id.encode("latin-1")))
                response_headers.append((b"x-process-time-ms", f"{duration_ms:.2f}".encode("latin-1")))
                response_headers.extend(_SECURITY_HEADERS)
                if settings.ENVIRONMENT == "production":
                    response_headers.append(_HSTS_HEADER)
                message["headers"] = response_headers
            await send(message)

        with bind_context(ctx):
            await self.app(scope, receive, send_wrapper)
