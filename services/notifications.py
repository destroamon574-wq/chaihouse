"""Внутренние уведомления пользователей."""
from __future__ import annotations

from core import utc_stamp
from database import get_db


def create_notification(user_id: int | None, title: str, body: str, link: str | None = None) -> None:
    if not user_id:
        return
    get_db().execute(
        "INSERT INTO notifications(user_id, title, body, link, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, title[:120], body[:500], link, utc_stamp()),
    )


def unread_count(user_id: int) -> int:
    row = get_db().execute(
        "SELECT COUNT(*) AS n FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,)
    ).fetchone()
    return row["n"] if row else 0


def list_notifications(user_id: int, limit: int = 50) -> list:
    return get_db().execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()


def mark_all_read(user_id: int) -> None:
    db = get_db()
    db.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0", (user_id,))
    db.commit()


def mark_read(notification_id: int, user_id: int) -> bool:
    db = get_db()
    cursor = db.execute(
        "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
        (notification_id, user_id),
    )
    db.commit()
    return cursor.rowcount > 0
