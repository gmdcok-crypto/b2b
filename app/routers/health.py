from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/")
def root() -> dict[str, str]:
    return {"app": get_settings().app_name, "status": "ok"}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": get_settings().app_name}
