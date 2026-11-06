from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.auth.router import users_router
from app.modules.catalog.router import categories_router, lots_router, products_router
from app.modules.partners.router import router as partners_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(categories_router)
api_router.include_router(products_router)
api_router.include_router(lots_router)
api_router.include_router(partners_router)

