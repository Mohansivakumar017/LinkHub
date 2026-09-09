from fastapi import APIRouter

from app.presentation.api.v1.routers.admin import router as admin_router
from app.presentation.api.v1.routers.analytics import router as analytics_router
from app.presentation.api.v1.routers.api_keys import router as api_keys_router
from app.presentation.api.v1.routers.auth import router as auth_router
from app.presentation.api.v1.routers.health import router as health_router
from app.presentation.api.v1.routers.organizations import router as organizations_router
from app.presentation.api.v1.routers.urls import router as urls_router
from app.presentation.api.v1.routers.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(organizations_router)
api_router.include_router(urls_router)
api_router.include_router(analytics_router)
api_router.include_router(admin_router)
api_router.include_router(api_keys_router)
api_router.include_router(users_router)
