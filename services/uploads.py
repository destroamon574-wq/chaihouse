"""Безопасная загрузка изображений."""
from __future__ import annotations

import secrets
from pathlib import Path

from flask import current_app, url_for

from core import detect_image_type

MAX_IMAGE_BYTES = 3 * 1024 * 1024
ALLOWED_EXT = {"png", "jpg", "jpeg", "webp"}


class UploadError(ValueError):
    pass


def save_image(file_storage, prefix: str = "img") -> str:
    if file_storage is None or not getattr(file_storage, "filename", ""):
        raise UploadError("Выберите файл изображения.")
    filename = file_storage.filename
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXT:
        raise UploadError("Поддерживаются только PNG, JPEG и WebP.")
    data = file_storage.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise UploadError("Файл больше 3 МБ.")
    if not data:
        raise UploadError("Файл пустой.")
    if detect_image_type(data, filename) is None:
        raise UploadError("Содержимое файла не похоже на изображение PNG, JPEG или WebP.")
    safe_prefix = "".join(ch for ch in prefix if ch.isalnum() or ch in "-_")[:24] or "img"
    stored_name = f"{safe_prefix}-{secrets.token_hex(10)}.{ext}"
    directory = Path(current_app.config["UPLOAD_DIR"])
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / stored_name
    target.write_bytes(data)
    return f"uploads/{stored_name}"


def delete_upload(path: str | None) -> None:
    if not path or not path.startswith("uploads/"):
        return
    name = path.split("/", 1)[1]
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return
    target = Path(current_app.config["UPLOAD_DIR"]) / name
    try:
        if target.parent == Path(current_app.config["UPLOAD_DIR"]) and target.exists():
            target.unlink()
    except OSError:
        pass


def image_url(path: str | None) -> str:
    if not path:
        return url_for("static", filename="img/placeholder.svg")
    if path.startswith("uploads/"):
        return url_for("public.media", filename=path.split("/", 1)[1])
    if path.startswith("img/"):
        return url_for("static", filename=path)
    return url_for("static", filename="img/placeholder.svg")
