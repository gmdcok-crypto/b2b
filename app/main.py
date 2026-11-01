from fastapi import FastAPI

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.routers.health import router as health_router

settings = get_settings()
app = FastAPI(title=settings.app_name)
register_exception_handlers(app)
app.include_router(health_router)
