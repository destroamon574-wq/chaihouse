"""Резервная копия базы ЧайHouse — запуск вручную или из планировщика.

Примеры:
    python scripts/backup_db.py
    flask --app app backup-db
Планировщик Windows (ежедневно в 21:00):
    schtasks /Create /SC DAILY /ST 21:00 /TN "ЧайHouse бэкап" ^
      /TR "python C:\\...\\scripts\\backup_db.py"
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from services.backup import create_backup  # noqa: E402


def main() -> int:
    app = create_app()
    with app.app_context():
        target, kept = create_backup()
        print(f"Копия создана: {target}")
        print(f"Всего копий: {kept}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
