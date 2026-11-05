import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware import RequestContextMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging

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

    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=None if is_prod else f"{settings.API_V1_STR}/openapi.json",
        docs_url=None if is_prod else f"{settings.API_V1_STR}/docs",
        redoc_url=None if is_prod else f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan,
    )

    # Global Exception Handlers
    register_exception_handlers(application)

    # Middleware Pipeline
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestContextMiddleware)

    # Routers
    application.include_router(api_router, prefix=settings.API_V1_STR)

    @application.get("/", tags=["Root"])
    async def root_info() -> dict[str, str]:
        info = {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
        }
        if not is_prod:
            info["docs"] = f"{settings.API_V1_STR}/docs"
        return info

    return application


app = create_app()
