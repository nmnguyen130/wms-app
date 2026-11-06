import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.middleware import RateLimitMiddleware, RequestContextMiddleware
from app.api.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import register_exception_handlers
from app.utils.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting %s v%s in %s mode...", settings.PROJECT_NAME, settings.VERSION, settings.ENVIRONMENT)
    yield
    logger.info("Shutting down %s, releasing database connection pool...", settings.PROJECT_NAME)
    await engine.dispose()


def create_app() -> FastAPI:
    is_prod = settings.ENVIRONMENT == "production"

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=None if is_prod else f"{settings.API_V1_STR}/openapi.json",
        docs_url=None if is_prod else f"{settings.API_V1_STR}/docs",
        redoc_url=None if is_prod else f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan,
    )

    register_exception_handlers(app)

    # Middleware execution order in Starlette (last added = outermost):
    # Incoming request: CORSMiddleware -> RequestContextMiddleware -> RateLimitMiddleware -> Endpoint
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
        max_age=600,
    )

    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.get("/", tags=["Root"])
    async def root_info() -> dict[str, str]:
        info = {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
        }
        if not is_prod:
            info["docs"] = f"{settings.API_V1_STR}/docs"
        return info

    return app


app = create_app()
