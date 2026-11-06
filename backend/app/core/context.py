from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True)
class RequestContext:
    """Per-request metadata. user_id is filled after token authentication."""

    request_id: str
    client_ip: str = "127.0.0.1"
    user_id: UUID | None = None


_current_context: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


def get_current_context() -> RequestContext | None:
    return _current_context.get()


@contextmanager
def bind_context(ctx: RequestContext) -> Iterator[RequestContext]:
    token = _current_context.set(ctx)
    try:
        yield ctx
    finally:
        _current_context.reset(token)
