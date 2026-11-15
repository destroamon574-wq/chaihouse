"""Резервное копирование базы данных SQLite."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app

KEEP_BACKUPS = 14


def backup_dir() -> Path:
    path = Path(current_app.config["DATABASE_PATH"])
    directory = path.parent / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def create_backup(keep: int = KEEP_BACKUPS) -> tuple[Path, int]:
    """Создаёт консистентную копию базы и удаляет самые старые сверх лимита.

    Возвращает (путь к копии, сколько копий осталось).
    """
    source_path = Path(current_app.config["DATABASE_PATH"])
    directory = backup_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = directory / f"chaihouse-{stamp}.db"

    source = sqlite3.connect(str(source_path))
    destination = sqlite3.connect(str(target))
    try:
        source.backup(destination)
        destination.commit()
    finally:
        destination.close()
        source.close()

    backups = sorted(directory.glob("chaihouse-*.db"))
    if keep and len(backups) > keep:
        for old in backups[:-keep]:
            old.unlink(missing_ok=True)

    remaining = len(list(directory.glob("chaihouse-*.db")))
    return target, remaining
