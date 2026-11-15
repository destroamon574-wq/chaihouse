"""Залы, галерея, отзывы и настройки заведения."""
from __future__ import annotations

import json
import sqlite3

from core import (
    clean_text, get_settings, utc_stamp, valid_email,
)
from database import get_db
from services.audit import log_action
from services.common import paginate
from services.uploads import delete_upload

GALLERY_CATEGORIES = {"interior": "Интерьер", "food": "Блюда", "details": "Детали"}
PRESET_IMAGES = [
    ("img/hero-interior.svg", "Основной зал"),
    ("img/hall-main.svg", "Столы у окна"),
    ("img/hall-veranda.svg", "Веранда"),
    ("img/hall-vip.svg", "VIP-зал"),
    ("img/hall-banquet.svg", "Банкетный зал"),
    ("img/detail-lamp.svg", "Латунный свет"),
    ("img/detail-ornament.svg", "Узор"),
    ("img/detail-table.svg", "Сервировка"),
]


def get_halls(include_inactive: bool = False) -> list:
    sql = (
        "SELECT h.*, (SELECT COUNT(*) FROM dining_tables t WHERE t.hall_id = h.id AND t.is_active = 1) "
        "AS table_count, (SELECT COALESCE(SUM(t.seats), 0) FROM dining_tables t "
        "WHERE t.hall_id = h.id AND t.is_active = 1) AS seats_total FROM halls h"
    )
    if not include_inactive:
        sql += " WHERE h.is_active = 1"
    sql += " ORDER BY h.sort_order, h.name"
    halls = []
    for row in get_db().execute(sql).fetchall():
        item = dict(row)
        try:
            item["features_list"] = json.loads(item.get("features") or "[]")
        except (ValueError, TypeError):
            item["features_list"] = []
        halls.append(item)
    return halls


def get_hall(slug: str, include_inactive: bool = False):
    sql = "SELECT * FROM halls WHERE slug = ?"
    if not include_inactive:
        sql += " AND is_active = 1"
    row = get_db().execute(sql, (slug,)).fetchone()
    if not row:
        return None
    item = dict(row)
    try:
        item["features_list"] = json.loads(item.get("features") or "[]")
    except (ValueError, TypeError):
        item["features_list"] = []
    tables = get_db().execute(
        "SELECT * FROM dining_tables WHERE hall_id = ? AND is_active = 1 ORDER BY seats, id", (row["id"],)
    ).fetchall()
    item["tables"] = tables
    item["seats_total"] = sum(table["seats"] for table in tables)
    return item


def get_hall_by_id(hall_id: int):
    return get_db().execute("SELECT * FROM halls WHERE id = ?", (hall_id,)).fetchone()


def update_hall(hall_id: int, form, image_path: str | None = None) -> dict[str, str]:
    db = get_db()
    hall = get_hall_by_id(hall_id)
    if not hall:
        return {"_": "Зал не найден."}
    errors: dict[str, str] = {}
    name = clean_text(form.get("name"), 80)
    tagline = clean_text(form.get("tagline"), 120)
    description = (form.get("description") or "").strip()
    try:
        capacity = int(form.get("capacity") or 0)
    except (TypeError, ValueError):
        capacity = 0
    try:
        min_spend = int(form.get("min_spend") or 0)
    except (TypeError, ValueError):
        min_spend = -1
    features_raw = (form.get("features") or "").strip()
    features = [clean_text(line, 80) for line in features_raw.replace(",", "\n").splitlines() if clean_text(line, 80)]
    if len(name) < 2:
        errors["name"] = "Укажите название зала."
    if len(description) < 20:
        errors["description"] = "Описание — минимум 20 символов."
    if not 1 <= capacity <= 200:
        errors["capacity"] = "Вместимость — от 1 до 200 гостей."
    if not 0 <= min_spend <= 1_000_000:
        errors["min_spend"] = "Минимальный чек — от 0 до 1 000 000 ₽."
    if errors:
        return errors
    db.execute(
        "UPDATE halls SET name = ?, tagline = ?, description = ?, capacity = ?, min_spend = ?, "
        "features = ?, image = ?, sort_order = ? WHERE id = ?",
        (name, tagline, description, capacity, min_spend, json.dumps(features, ensure_ascii=False),
         image_path or hall["image"], form.get("sort_order", type=int) or 0, hall_id),
    )
    db.commit()
    log_action("hall.updated", "hall", hall_id, {"name": name})
    db.commit()
    return {}


def toggle_hall(hall_id: int) -> bool:
    db = get_db()
    hall = get_hall_by_id(hall_id)
    if not hall:
        raise ValueError("Зал не найден.")
    new_value = 0 if hall["is_active"] else 1
    db.execute("UPDATE halls SET is_active = ? WHERE id = ?", (new_value, hall_id))
    db.commit()
    log_action("hall.toggled", "hall", hall_id, {"is_active": new_value})
    db.commit()
    return bool(new_value)


def add_table(hall_id: int, form) -> tuple[int | None, dict[str, str]]:
    db = get_db()
    if not get_hall_by_id(hall_id):
        return None, {"_": "Зал не найден."}
    name = clean_text(form.get("name"), 40)
    try:
        seats = int(form.get("seats") or 0)
    except (TypeError, ValueError):
        seats = 0
    errors = {}
    if len(name) < 1:
        errors["name"] = "Укажите название стола."
    if not 1 <= seats <= 30:
        errors["seats"] = "Мест за столом — от 1 до 30."
    if errors:
        return None, errors
    try:
        cursor = db.execute("INSERT INTO dining_tables(hall_id, name, seats) VALUES (?, ?, ?)",
                            (hall_id, name, seats))
        db.commit()
    except sqlite3.IntegrityError:
        return None, {"name": "Стол с таким названием уже есть в зале."}
    log_action("table.created", "table", cursor.lastrowid, {"hall_id": hall_id, "seats": seats})
    db.commit()
    return cursor.lastrowid, {}


def toggle_table(table_id: int) -> bool:
    db = get_db()
    table = db.execute("SELECT * FROM dining_tables WHERE id = ?", (table_id,)).fetchone()
    if not table:
        raise ValueError("Стол не найден.")
    new_value = 0 if table["is_active"] else 1
    db.execute("UPDATE dining_tables SET is_active = ? WHERE id = ?", (new_value, table_id))
    db.commit()
    log_action("table.toggled", "table", table_id, {"is_active": new_value})
    db.commit()
    return bool(new_value)


def get_tables_admin() -> list:
    return get_db().execute(
        "SELECT t.*, h.name AS hall_name, h.slug AS hall_slug FROM dining_tables t "
        "JOIN halls h ON h.id = t.hall_id ORDER BY h.sort_order, t.seats, t.id"
    ).fetchall()


def get_gallery(category: str | None = None, include_inactive: bool = False) -> list:
    where, params = [], []
    if not include_inactive:
        where.append("is_active = 1")
    if category in GALLERY_CATEGORIES:
        where.append("category = ?")
        params.append(category)
    sql = "SELECT * FROM gallery_images"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY sort_order, id"
    return get_db().execute(sql, params).fetchall()


def add_gallery(form, image_path: str) -> tuple[int | None, dict[str, str]]:
    db = get_db()
    title = clean_text(form.get("title"), 100)
    alt = clean_text(form.get("alt") or title, 180)
    category = form.get("category") or "interior"
    errors = {}
    if len(title) < 2:
        errors["title"] = "Укажите подпись."
    if len(alt) < 5:
        errors["alt"] = "Alt-текст — минимум 5 символов."
    if category not in GALLERY_CATEGORIES:
        errors["category"] = "Выберите категорию."
    if errors:
        return None, errors
    cursor = db.execute(
        "INSERT INTO gallery_images(title, alt, image, category, sort_order, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (title, alt, image_path, category, form.get("sort_order", type=int) or 0, utc_stamp()),
    )
    db.commit()
    log_action("gallery.created", "gallery", cursor.lastrowid, {"title": title})
    db.commit()
    return cursor.lastrowid, {}


def delete_gallery(image_id: int) -> None:
    db = get_db()
    row = db.execute("SELECT * FROM gallery_images WHERE id = ?", (image_id,)).fetchone()
    if not row:
        return
    db.execute("DELETE FROM gallery_images WHERE id = ?", (image_id,))
    db.commit()
    delete_upload(row["image"])
    log_action("gallery.deleted", "gallery", image_id, {"title": row["title"]})
    db.commit()


def list_reviews(status: str = "published", page: int | str | None = 1, per_page: int = 6):
    db = get_db()
    if status not in ("pending", "published", "rejected", "all"):
        status = "published"
    where_sql = "" if status == "all" else " WHERE status = ?"
    params = [] if status == "all" else [status]
    total = db.execute("SELECT COUNT(*) AS n FROM reviews" + where_sql, params).fetchone()["n"]
    pages = paginate(page, total, per_page)
    rows = db.execute(
        "SELECT * FROM reviews" + where_sql + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [pages["per_page"], pages["offset"]],
    ).fetchall()
    return rows, pages


def review_summary() -> dict:
    row = get_db().execute(
        "SELECT COUNT(*) AS n, COALESCE(AVG(rating), 0) AS avg FROM reviews WHERE status = 'published'"
    ).fetchone()
    distribution = {star: 0 for star in range(1, 6)}
    for item in get_db().execute(
        "SELECT rating, COUNT(*) AS n FROM reviews WHERE status = 'published' GROUP BY rating"
    ).fetchall():
        distribution[item["rating"]] = item["n"]
    return {"count": row["n"], "avg": round(row["avg"] or 0, 1), "distribution": distribution}


def top_reviews(limit: int = 3, min_rating: int = 5) -> list:
    """Лучшие опубликованные отзывы — для главной страницы."""
    return get_db().execute(
        "SELECT * FROM reviews WHERE status = 'published' AND rating >= ? "
        "ORDER BY rating DESC, created_at DESC LIMIT ?",
        (min_rating, limit),
    ).fetchall()


def hall_reviews(hall_id: int, limit: int = 3) -> list:
    """Отзывы гостей, оставленные к броням в конкретном зале."""
    return get_db().execute(
        "SELECT r.*, h.name AS hall_name FROM reviews r "
        "JOIN bookings b ON b.id = r.booking_id JOIN halls h ON h.id = b.hall_id "
        "WHERE r.status = 'published' AND b.hall_id = ? "
        "ORDER BY r.rating DESC, r.created_at DESC LIMIT ?",
        (hall_id, limit),
    ).fetchall()


def create_review(user, form) -> tuple[bool, dict[str, str]]:
    db = get_db()
    try:
        rating = int(form.get("rating") or 0)
    except (TypeError, ValueError):
        rating = 0
    text = (form.get("text") or "").strip()
    errors = {}
    if not 1 <= rating <= 5:
        errors["rating"] = "Поставьте оценку от 1 до 5."
    if len(text) < 10:
        errors["text"] = "Расскажите чуть подробнее — минимум 10 символов."
    if len(text) > 1200:
        errors["text"] = "Отзыв — не более 1200 символов."
    if errors:
        return False, errors
    db.execute(
        "INSERT INTO reviews(user_id, author_name, rating, text, status, created_at) "
        "VALUES (?, ?, ?, ?, 'pending', ?)",
        (user["id"], user["name"][:80], rating, text, utc_stamp()),
    )
    db.commit()
    log_action("review.created", "review", None, {"rating": rating})
    db.commit()
    return True, {}


def moderate_review(review_id: int, action: str, reply: str = "") -> tuple[bool, str]:
    db = get_db()
    review = db.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
    if not review:
        return False, "Отзыв не найден."
    status_map = {"publish": "published", "reject": "rejected", "pending": "pending"}
    if action not in status_map and action != "save":
        return False, "Неизвестное действие."
    reply = clean_text(reply, 500)
    new_status = review["status"] if action == "save" else status_map[action]
    db.execute(
        "UPDATE reviews SET status = ?, admin_reply = ?, moderated_by = ?, moderated_at = ? WHERE id = ?",
        (new_status, reply or review["admin_reply"], None, utc_stamp(), review_id),
    )
    from flask import g
    if g.get("user"):
        db.execute("UPDATE reviews SET moderated_by = ? WHERE id = ?", (g.user["id"], review_id))
    db.commit()
    log_action("review.moderated", "review", review_id, {"action": action})
    db.commit()
    return True, ""


def update_settings(form) -> dict[str, str]:
    db = get_db()
    errors: dict[str, str] = {}
    values = {
        "restaurant_name": clean_text(form.get("restaurant_name"), 80),
        "tagline": clean_text(form.get("tagline"), 160),
        "phone": clean_text(form.get("phone"), 40),
        "email": clean_text(form.get("email"), 120),
        "address": clean_text(form.get("address"), 220),
        "address_short": clean_text(form.get("address_short"), 120),
        "hours": clean_text(form.get("hours"), 80),
        "booking_note": clean_text(form.get("booking_note"), 300),
        "legal_name": clean_text(form.get("legal_name"), 120),
        "telegram_bot_token": clean_text(form.get("telegram_bot_token"), 80),
        "telegram_chat_id": clean_text(form.get("telegram_chat_id"), 40),
    }
    if len(values["restaurant_name"]) < 2:
        errors["restaurant_name"] = "Укажите название."
    if values["email"] and not valid_email(values["email"]):
        errors["email"] = "Проверьте email."
    for key in ("lat", "lng"):
        raw = (form.get(key) or "").strip()
        try:
            number = float(raw)
            if not -180 <= number <= 180:
                raise ValueError
            if key == "lat" and not -90 <= number <= 90:
                raise ValueError
            values[key] = f"{number:.6f}"
        except (TypeError, ValueError):
            errors[key] = "Проверьте координаты."
    try:
        avg_check = int(form.get("avg_check") or 0)
        if not 0 <= avg_check <= 100000:
            raise ValueError
        values["avg_check"] = str(avg_check)
    except (TypeError, ValueError):
        errors["avg_check"] = "Средний чек — от 0 до 100 000 ₽."
    try:
        max_guests = int(form.get("max_guests") or 0)
        if not 1 <= max_guests <= 40:
            raise ValueError
        values["max_guests"] = str(max_guests)
    except (TypeError, ValueError):
        errors["max_guests"] = "Максимум гостей — от 1 до 40."
    if errors:
        return errors
    for key, value in values.items():
        db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (key, value))
    db.commit()
    from flask import g
    g.pop("settings", None)
    log_action("settings.updated", "settings", "main", {"keys": list(values)})
    db.commit()
    return {}
