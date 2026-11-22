"""단가 변경요청 공문 파일 저장."""

import re
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.errors import AppError

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".doc", ".docx", ".hwp"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
SAFE_NAME = re.compile(r"[^A-Za-z0-9._\-가-힣]+")


def upload_root() -> Path:
    configured = (get_settings().upload_dir or "").strip()
    root = Path(configured) if configured else Path(__file__).resolve().parents[2] / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_filename(name: str) -> str:
    cleaned = SAFE_NAME.sub("_", (name or "file").strip())[:120].strip("._")
    return cleaned or "file"


async def save_price_attachment(file: UploadFile) -> tuple[str, str, str, int]:
    original = safe_filename(file.filename or "공문.pdf")
    suffix = Path(original).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise AppError("invalid_file", "공문은 PDF, 이미지, DOC, HWP만 첨부할 수 있습니다.")
    raw = await file.read()
    if not raw:
        raise AppError("invalid_file", "빈 파일은 첨부할 수 없습니다.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise AppError("invalid_file", "첨부 파일은 10MB 이하여야 합니다.")
    stored = uuid.uuid4().hex + "_" + original
    path = upload_root() / stored
    path.write_bytes(raw)
    content_type = (file.content_type or "").strip()[:120]
    return original, stored, content_type, len(raw)


def attachment_path(stored_name: str) -> Path:
    path = upload_root() / stored_name
    if not path.is_file():
        raise AppError("not_found", "첨부 파일을 찾을 수 없습니다.", 404)
    return path
