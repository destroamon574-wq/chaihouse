"""Бронирования: доступность, создание, статусы, календарь."""
from __future__ import annotations

import calendar
import secrets
import sqlite3
from datetime import date, datetime, timedelta, timezone

from flask import current_app, g, session

from core import (
    clean_text, get_settings, normalize_phone, parse_iso_date, pretty_phone, ru_date,
    utc_stamp, valid_email,
)
from database import get_db
from services.audit import log_action
from services.common import paginate
from services.notifications import create_notification

OCCASIONS = ("Ужин", "Встреча с друзьями", "День рождения", "Свидание",
             "Корпоратив", "Семейный праздник", "Другое")
ACTIVE_STATUSES = ("pending", "confirmed")
ADMIN_TRANSITIONS = {
    "pending": {"confirmed", "declined", "cancelled"},
    "confirmed": {"completed", "cancelled"},
    "cancelled": set(),
    "declined": set(),
    "completed": set(),
}
GUEST_TRANSITIONS = {
    "pending": {"cancelled"},
    "confirmed": {"cancelled"},
}
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def moscow_now() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=3)


def today_local() -> date:
    return moscow_now().date()


def slot_times() -> list[str]:
    start = int(current_app.config.get("SLOT_START_HOUR", 12))
    end = int(current_app.config.get("SLOT_END_HOUR", 22))
    return [f"{hour:02d}:00" for hour in range(start, end + 1)]


def minutes_from_time(value: str) -> int | None:
    try:
        hours, minutes = value.split(":")
        total = int(hours) * 60 + int(minutes)
    except (ValueError, AttributeError):
        return None
    return total if 0 <= total < 1440 else None


def time_from_minutes(value: int) -> str:
    value = value % 1440
    return f"{value // 60:02d}:{value % 60:02d}"


def slot_end(value: str) -> str:
    minutes = minutes_from_time(value)
    if minutes is None:
        return ""
    return time_from_minutes(minutes + int(current_app.config.get("BOOKING_DURATION_MIN", 120)))


def _code() -> str:
    return "CH-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


def _unique_code(db) -> str:
    for _ in range(12):
        code = _code()
        if not db.execute("SELECT 1 FROM bookings WHERE code = ?", (code,)).fetchone():
            return code
    return "CH-" + secrets.token_hex(6).upper()


def get_booking(code: str, with_details: bool = True):
    if not code or len(code) > 20:
        return None
    sql = "SELECT b.* FROM bookings b WHERE b.code = ?"
    if with_details:
        sql = (
            "SELECT b.*, h.name AS hall_name, h.slug AS hall_slug, h.image AS hall_image, "
            "t.name AS table_name, t.seats AS table_seats "
            "FROM bookings b JOIN halls h ON h.id = b.hall_id "
            "JOIN dining_tables t ON t.id = b.table_id WHERE b.code = ?"
        )
    return get_db().execute(sql, (code,)).fetchone()


def get_booking_by_id(booking_id: int):
    return get_db().execute(
        "SELECT b.*, h.name AS hall_name, t.name AS table_name, t.seats AS table_seats "
        "FROM bookings b JOIN halls h ON h.id = b.hall_id "
        "JOIN dining_tables t ON t.id = b.table_id WHERE b.id = ?",
        (booking_id,),
    ).fetchone()


def remember_booking_access(code: str) -> None:
    codes = [value for value in session.get("booking_codes", []) if value != code]
    codes.append(code)
    session["booking_codes"] = codes[-20:]


def has_booking_access(booking, user=None) -> bool:
    if booking is None:
        return False
    user = user if user is not None else g.get("user")
    if user and user["role"] in ("admin", "owner"):
        return True
    if user and booking["user_id"] == user["id"]:
        return True
    return booking["code"] in session.get("booking_codes", [])


def _free_tables(db, hall_id: int, date_value: str, start_min: int, end_min: int,
                 guests: int = 1) -> list:
    rows = db.execute(
        "SELECT t.* FROM dining_tables t WHERE t.hall_id = ? AND t.is_active = 1 AND t.seats >= ? "
        "ORDER BY t.seats, t.id",
        (hall_id, guests),
    ).fetchall()
    free = []
    for table in rows:
        conflict = db.execute(
            "SELECT 1 FROM bookings WHERE table_id = ? AND date = ? "
            "AND status IN ('pending', 'confirmed') AND start_min < ? AND ? < end_min LIMIT 1",
            (table["id"], date_value, end_min, start_min),
        ).fetchone()
        if not conflict:
            free.append(table)
    return free


def _as_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def create_booking(form, user_id: int | None = None) -> tuple[dict | None, dict[str, str]]:
    db = get_db()
    settings = get_settings()
    errors: dict[str, str] = {}

    hall_id = _as_int(form.get("hall_id"))
    hall = db.execute("SELECT * FROM halls WHERE id = ? AND is_active = 1", (hall_id,)).fetchone() if hall_id else None
    if not hall:
        errors["hall_id"] = "Выберите зал."

    date_raw = (form.get("date") or "").strip()
    date_value = parse_iso_date(date_raw)
    today = today_local()
    if not date_value:
        errors["date"] = "Выберите дату."
    elif date_value < today:
        errors["date"] = "Нельзя забронировать прошедшую дату."
    elif date_value > today + timedelta(days=int(current_app.config.get("BOOKING_DAYS_AHEAD", 90))):
        errors["date"] = "Бронирование доступно не более чем на 90 дней вперёд."

    time_value = (form.get("time") or "").strip()
    if time_value not in slot_times():
        errors["time"] = "Выберите время из доступных слотов."
        start_min = None
    else:
        start_min = minutes_from_time(time_value)
    duration = int(current_app.config.get("BOOKING_DURATION_MIN", 120))
    end_min = (start_min or 0) + duration
    now_local = moscow_now()
    if date_value == today and start_min is not None:
        if start_min <= now_local.hour * 60 + now_local.minute + 30:
            errors["time"] = "Этот слот уже начался. Выберите более позднее время или другую дату."

    try:
        guests = int(form.get("guests") or 0)
    except (TypeError, ValueError):
        guests = 0
    max_guests = int(settings.get("max_guests", 20))
    if not 1 <= guests <= max_guests:
        errors["guests"] = f"Количество гостей — от 1 до {max_guests}."

    name = clean_text(form.get("name"), 80)
    if len(name) < 2:
        errors["name"] = "Укажите имя (минимум 2 символа)."
    phone_raw = (form.get("phone") or "").strip()
    phone = normalize_phone(phone_raw)
    if not phone:
        errors["phone"] = "Телефон в формате +7 999 123-45-67."
    email_raw = (form.get("email") or "").strip().lower()
    if email_raw and not valid_email(email_raw):
        errors["email"] = "Проверьте email."
    occasion = (form.get("occasion") or "").strip()
    if occasion and occasion not in OCCASIONS:
        errors["occasion"] = "Выберите повод из списка."
    comment = (form.get("comment") or "").strip()
    if len(comment) > 500:
        errors["comment"] = "Комментарий — не более 500 символов."
    if not form.get("consent"):
        errors["consent"] = "Нужно согласие на обработку персональных данных."

    table_id = _as_int(form.get("table_id"))
    table = None
    if table_id:
        table = db.execute(
            "SELECT * FROM dining_tables WHERE id = ? AND hall_id = ? AND is_active = 1",
            (table_id, hall_id or 0),
        ).fetchone()
        if not table:
            errors["table_id"] = "Этот стол недоступен в выбранном зале."
        elif guests and table["seats"] < guests:
            errors["table_id"] = f"Стол рассчитан на {table['seats']} гостей — выберите другой."
    elif hall and date_value and start_min is not None and not errors.get("date") and not errors.get("time"):
        free = _free_tables(db, hall["id"], date_value.isoformat(), start_min, end_min, guests or 1)
        table = free[0] if free else None
        if not table:
            errors["table_id"] = "На это время в зале нет свободных столов. Выберите другой слот."

    if errors:
        return None, errors

    db.commit()
    try:
        db.execute("BEGIN IMMEDIATE")
        conflict = db.execute(
            "SELECT 1 FROM bookings WHERE table_id = ? AND date = ? "
            "AND status IN ('pending', 'confirmed') AND start_min < ? AND ? < end_min LIMIT 1",
            (table["id"], date_value.isoformat(), end_min, start_min),
        ).fetchone()
        if conflict:
            db.rollback()
            return None, {"table_id": "Этот стол только что забронировали. Выберите другой слот."}
        code = _unique_code(db)
        now = utc_stamp()
        cursor = db.execute(
            "INSERT INTO bookings(code, user_id, hall_id, table_id, guest_name, guest_phone, guest_email, "
            "date, time, start_min, end_min, guests_count, occasion, comment, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
            (code, user_id, hall_id, table["id"], name, phone, email_raw or None,
             date_value.isoformat(), time_value, start_min, end_min, guests, occasion or None,
             comment or None, now, now),
        )
        log_action(
            "booking.created", "booking", code,
            {"hall_id": hall_id, "table_id": table["id"], "date": date_value.isoformat(),
             "time": time_value, "guests": guests},
        )
        if user_id:
            create_notification(
                user_id, "Заявка на бронь принята",
                f"{ru_date(date_value, 'day')} в {time_value}, {hall['name']}, {table['name']}. "
                "Подтвердим бронь в ближайшее время.",
                f"/account/bookings/{code}",
            )
        admin_rows = db.execute("SELECT id FROM users WHERE role IN ('admin', 'owner') AND is_active = 1").fetchall()
        for admin in admin_rows:
            create_notification(
                admin["id"], "Новая бронь",
                f"{name}: {ru_date(date_value, 'day')} в {time_value}, {hall['name']}, {guests} чел.",
                "/admin/bookings?status=pending",
            )
        db.commit()
        remember_booking_access(code)
        try:
            from services.notify import notify_admins_new_booking

            notify_admins_new_booking({
                "guest_name": name, "date": date_value.isoformat(), "time": time_value,
                "hall_name": hall["name"], "table_name": table["name"],
                "guests": guests, "code": code,
            })
        except Exception:
            pass
        return {
            "id": cursor.lastrowid, "code": code, "hall_name": hall["name"],
            "table_name": table["name"], "date": date_value.isoformat(), "time": time_value,
            "guests": guests,
        }, {}
    except sqlite3.IntegrityError:
        db.rollback()
        return None, {"table_id": "Этот слот уже занят. Выберите другое время."}
    except Exception:
        db.rollback()
        raise


def availability(hall_id: int, date_value: date) -> dict:
    db = get_db()
    tables = db.execute(
        "SELECT * FROM dining_tables WHERE hall_id = ? AND is_active = 1 ORDER BY seats, id",
        (hall_id,),
    ).fetchall()
    bookings = db.execute(
        "SELECT b.*, t.name AS table_name FROM bookings b JOIN dining_tables t ON t.id = b.table_id "
        "WHERE b.hall_id = ? AND b.date = ? AND b.status IN ('pending', 'confirmed')",
        (hall_id, date_value.isoformat()),
    ).fetchall()
    duration = int(current_app.config.get("BOOKING_DURATION_MIN", 120))
    now_local = moscow_now()
    is_today = date_value == today_local()
    slots = slot_times()
    grid = []
    for table in tables:
        cells = []
        for value in slots:
            start = minutes_from_time(value)
            end = start + duration
            conflict = next(
                (b for b in bookings if b["table_id"] == table["id"] and b["start_min"] < end and start < b["end_min"]),
                None,
            )
            past = bool(is_today and start <= now_local.hour * 60 + now_local.minute + 30)
            cells.append({
                "time": value,
                "end": time_from_minutes(end),
                "free": conflict is None and not past,
                "past": past,
                "booking": conflict,
            })
        grid.append({"table": table, "cells": cells})
    return {"tables": tables, "slots": slots, "grid": grid, "date": date_value,
            "bookings_count": len(bookings)}


def month_calendar(hall_id: int, year: int, month: int) -> dict:
    db = get_db()
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    rows = db.execute(
        "SELECT date, COUNT(*) AS n FROM bookings WHERE hall_id = ? AND date BETWEEN ? AND ? "
        "AND status IN ('pending', 'confirmed', 'completed') GROUP BY date",
        (hall_id, first.isoformat(), last.isoformat()),
    ).fetchall()
    counts = {row["date"]: row["n"] for row in rows}
    table_count = max(1, db.execute(
        "SELECT COUNT(*) AS n FROM dining_tables WHERE hall_id = ? AND is_active = 1", (hall_id,)
    ).fetchone()["n"])
    today = today_local()
    max_day = today + timedelta(days=int(current_app.config.get("BOOKING_DAYS_AHEAD", 90)))
    weeks = []
    calendar_rows = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
    for week in calendar_rows:
        rendered = []
        for day in week:
            if day.month != month:
                rendered.append(None)
                continue
            count = counts.get(day.isoformat(), 0)
            if count == 0:
                level = "free"
            elif count >= table_count:
                level = "busy"
            else:
                level = "some"
            rendered.append({
                "date": day, "day": day.day, "count": count, "level": level,
                "past": day < today, "today": day == today, "bookable": today <= day <= max_day,
            })
        weeks.append(rendered)
    prev_month = (first - timedelta(days=1))
    next_month = (last + timedelta(days=1))
    return {
        "year": year, "month": month, "weeks": weeks, "weekdays": ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"),
        "prev": {"year": prev_month.year, "month": prev_month.month},
        "next": {"year": next_month.year, "month": next_month.month},
        "counts": counts,
    }


def list_user_bookings(user_id: int, scope: str = "upcoming", status: str | None = None) -> list:
    db = get_db()
    where = ["b.user_id = ?"]
    params: list = [user_id]
    today = today_local().isoformat()
    if scope == "upcoming":
        where.append("b.date >= ? AND b.status IN ('pending', 'confirmed')")
        params.append(today)
    elif scope == "history":
        where.append("(b.date < ? OR b.status IN ('cancelled', 'declined', 'completed'))")
        params.append(today)
    if status in ("pending", "confirmed", "cancelled", "declined", "completed"):
        where.append("b.status = ?")
        params.append(status)
    order = "b.date ASC, b.time ASC" if scope == "upcoming" else "b.date DESC, b.time DESC"
    return db.execute(
        "SELECT b.*, h.name AS hall_name, h.slug AS hall_slug, t.name AS table_name "
        "FROM bookings b JOIN halls h ON h.id = b.hall_id JOIN dining_tables t ON t.id = b.table_id "
        "WHERE " + " AND ".join(where) + " ORDER BY " + order,
        params,
    ).fetchall()


def upcoming_for_user(user_id: int, limit: int = 3) -> list:
    return get_db().execute(
        "SELECT b.*, h.name AS hall_name, t.name AS table_name FROM bookings b "
        "JOIN halls h ON h.id = b.hall_id JOIN dining_tables t ON t.id = b.table_id "
        "WHERE b.user_id = ? AND b.date >= ? AND b.status IN ('pending', 'confirmed') "
        "ORDER BY b.date, b.time LIMIT ?",
        (user_id, today_local().isoformat(), limit),
    ).fetchall()


def list_all_bookings(status: str | None = None, date_value: str | None = None,
                      q: str | None = None, page: int | str | None = 1) -> tuple[list, dict]:
    db = get_db()
    where, params = [], []
    if status in ("pending", "confirmed", "cancelled", "declined", "completed"):
        where.append("b.status = ?")
        params.append(status)
    if date_value and parse_iso_date(date_value):
        where.append("b.date = ?")
        params.append(date_value)
    if q:
        term = f"%{q.strip()[:80]}%"
        where.append("(b.guest_name LIKE ? OR b.guest_phone LIKE ? OR b.code LIKE ?)")
        params.extend([term, term, term])
    where_sql = " WHERE " + " AND ".join(where) if where else ""
    total = db.execute("SELECT COUNT(*) AS n FROM bookings b" + where_sql, params).fetchone()["n"]
    pages = paginate(page, total, 15)
    rows = db.execute(
        "SELECT b.*, h.name AS hall_name, t.name AS table_name, t.seats AS table_seats "
        "FROM bookings b JOIN halls h ON h.id = b.hall_id "
        "JOIN dining_tables t ON t.id = b.table_id" + where_sql +
        " ORDER BY CASE b.status WHEN 'pending' THEN 0 WHEN 'confirmed' THEN 1 ELSE 2 END, "
        "b.date ASC, b.time ASC LIMIT ? OFFSET ?",
        params + [pages["per_page"], pages["offset"]],
    ).fetchall()
    return rows, pages


def bookings_for_day(date_value: str) -> list:
    return get_db().execute(
        "SELECT b.*, h.name AS hall_name, t.name AS table_name FROM bookings b "
        "JOIN halls h ON h.id = b.hall_id JOIN dining_tables t ON t.id = b.table_id "
        "WHERE b.date = ? AND b.status IN ('pending', 'confirmed') ORDER BY b.time",
        (date_value,),
    ).fetchall()


def admin_week_grid(start_day: date) -> dict:
    """Сетка недели для админки: залы × 7 дней с бронями внутри."""
    from datetime import timedelta

    db = get_db()
    end_day = start_day + timedelta(days=6)
    rows = db.execute(
        "SELECT b.id, b.code, b.date, b.time, b.guests_count, b.guest_name, b.status, "
        "b.hall_id, h.name AS hall_name, t.name AS table_name FROM bookings b "
        "JOIN halls h ON h.id = b.hall_id JOIN dining_tables t ON t.id = b.table_id "
        "WHERE b.date BETWEEN ? AND ? AND b.status IN ('pending', 'confirmed', 'completed') "
        "ORDER BY b.time",
        (start_day.isoformat(), end_day.isoformat()),
    ).fetchall()
    bookings_by_key: dict[tuple[int, str], list] = {}
    day_totals: dict[str, dict] = {}
    for row in rows:
        key = (row["hall_id"], row["date"])
        bookings_by_key.setdefault(key, []).append(row)
        day = day_totals.setdefault(row["date"], {"bookings": 0, "guests": 0})
        day["bookings"] += 1
        day["guests"] += row["guests_count"]
    halls = db.execute(
        "SELECT id, name, slug FROM halls WHERE is_active = 1 ORDER BY sort_order, name"
    ).fetchall()
    days = []
    for offset in range(7):
        day = start_day + timedelta(days=offset)
        iso = day.isoformat()
        days.append({
            "date": day, "iso": iso,
            "label": f"{day.day} {('янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек')[day.month - 1]}",
            "weekday": ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")[day.weekday()],
            "is_today": day == today_local(),
            "totals": day_totals.get(iso, {"bookings": 0, "guests": 0}),
        })
    grid = []
    for hall in halls:
        cells = []
        for day in days:
            items = bookings_by_key.get((hall["id"], day["iso"]), [])
            cells.append({"items": items, "count": len(items)})
        grid.append({"hall": hall, "cells": cells})
    prev_week = start_day - timedelta(days=7)
    next_week = start_day + timedelta(days=7)
    week_start_monday = start_day - timedelta(days=start_day.weekday())
    return {
        "days": days, "grid": grid, "prev": prev_week.isoformat(), "next": next_week.isoformat(),
        "start": start_day.isoformat(), "title": ru_date(start_day),
        "monday": week_start_monday.isoformat(),
        "total_bookings": sum(day["totals"]["bookings"] for day in days),
        "total_guests": sum(day["totals"]["guests"] for day in days),
    }


def change_status(booking_id: int, new_status: str, actor, reason: str = "",
                  allow_public: bool = False) -> tuple[bool, str]:
    db = get_db()
    booking = get_booking_by_id(booking_id)
    if not booking:
        return False, "Бронь не найдена."
    if new_status not in ADMIN_TRANSITIONS:
        return False, "Недопустимый статус."
    role = actor["role"] if actor else "public"
    if role in ("admin", "owner"):
        allowed = ADMIN_TRANSITIONS.get(booking["status"], set())
    elif actor and booking["user_id"] == actor["id"]:
        allowed = GUEST_TRANSITIONS.get(booking["status"], set())
    elif allow_public:
        allowed = GUEST_TRANSITIONS.get(booking["status"], set())
    else:
        return False, "Недостаточно прав для изменения брони."
    if new_status not in allowed:
        return False, "Этот переход статуса недоступен."
    if new_status == "cancelled" and role not in ("admin", "owner") and is_past(booking):
        return False, "Прошедшую бронь нельзя отменить — позвоните нам."
    reason = clean_text(reason, 300)
    now = utc_stamp()
    confirmed_by = actor["id"] if new_status == "confirmed" and actor else None
    cancelled_by = actor["id"] if new_status in ("cancelled", "declined") and actor else None
    db.execute(
        "UPDATE bookings SET status = ?, cancel_reason = ?, updated_at = ?, confirmed_by = "
        "COALESCE(?, confirmed_by), cancelled_by = COALESCE(?, cancelled_by) WHERE id = ?",
        (new_status, reason or None, now, confirmed_by, cancelled_by, booking_id),
    )
    if booking["user_id"]:
        messages = {
            "confirmed": ("Бронь подтверждена",
                          f"Ждём вас {ru_date(booking['date'], 'day')} в {booking['time']}. "
                          f"{booking['hall_name']}, {booking['table_name']}."),
            "declined": ("Бронь отклонена", reason or "К сожалению, это время недоступно. Выберите другой слот."),
            "cancelled": ("Бронь отменена", reason or "Если это ошибка — создайте новую бронь."),
            "completed": ("Спасибо, что были у нас", "Будем рады видеть вас снова. Оставьте отзыв — нам важно мнение гостей."),
        }
        if new_status in messages:
            title, body = messages[new_status]
            create_notification(booking["user_id"], title, body, f"/account/bookings/{booking['code']}")
    if role in ("admin", "owner") and new_status in ("confirmed", "declined", "cancelled", "completed"):
        try:
            from services.notify import notify_guest_status

            notify_guest_status(booking, new_status, reason)
        except Exception:
            pass
    log_action(
        f"booking.{new_status}", "booking", booking["code"],
        {"from": booking["status"], "to": new_status, "reason": reason or None,
         "actor_role": role},
    )
    db.commit()
    return True, ""


def cancel_public(code: str, reason: str = "") -> tuple[bool, str]:
    booking = get_booking(code)
    if not booking or not has_booking_access(booking):
        return False, "Бронь не найдена."
    if booking["status"] not in ACTIVE_STATUSES:
        return False, "Эту бронь уже нельзя отменить."
    return change_status(booking["id"], "cancelled", g.get("user"), reason, allow_public=True)


def is_past(booking) -> bool:
    day = parse_iso_date(booking["date"])
    if not day:
        return False
    now = moscow_now()
    return day < now.date() or (day == now.date() and booking["end_min"] <= now.hour * 60 + now.minute)


def build_ics(booking) -> str:
    day = booking["date"].replace("-", "")
    start = booking["time"].replace(":", "") + "00"
    end_day_value = parse_iso_date(booking["date"]) + timedelta(days=1 if booking["end_min"] >= 1440 else 0)
    end_day = end_day_value.isoformat().replace("-", "")
    end = time_from_minutes(booking["end_min"]).replace(":", "") + "00"
    summary = f"ЧайHouse — бронь {booking['code']}"
    description = (
        f"{booking['hall_name']}, {booking['table_name']}. Гостей: {booking['guests_count']}. "
        f"Телефон ресторана: +7 (495) 120-48-18."
    )
    location = "Москва, Ходынский бульвар, 4, ТРЦ «Авиапарк», 3 этаж"
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ChaiHouse//Booking//RU",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "BEGIN:VEVENT",
        f"UID:{booking['code']}@chaihouse.example",
        f"DTSTAMP:{utc_stamp().replace('-', '').replace(':', '')}",
        f"DTSTART;TZID=Europe/Moscow:{day}T{start}",
        f"DTEND;TZID=Europe/Moscow:{end_day}T{end}",
        f"SUMMARY:{summary}", f"DESCRIPTION:{description}", f"LOCATION:{location}",
        "END:VEVENT", "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"
