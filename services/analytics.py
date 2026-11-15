"""Аналитика для владельца и админ-панели."""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from core import get_settings, money, ru_date, utc_stamp
from database import get_db

MONTH_LABEL = ("янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек")


def overview() -> dict:
    db = get_db()
    today = date.today()
    today_s = today.isoformat()
    week_start = (today - timedelta(days=6)).isoformat()
    month_start = today.replace(day=1).isoformat()
    stats = {}
    stats["today_total"] = db.execute(
        "SELECT COUNT(*) AS n FROM bookings WHERE date = ? AND status != 'cancelled'", (today_s,)
    ).fetchone()["n"]
    stats["today_guests"] = db.execute(
        "SELECT COALESCE(SUM(guests_count), 0) AS n FROM bookings WHERE date = ? "
        "AND status IN ('pending', 'confirmed', 'completed')",
        (today_s,),
    ).fetchone()["n"]
    stats["pending"] = db.execute("SELECT COUNT(*) AS n FROM bookings WHERE status = 'pending'").fetchone()[
        "n"
    ]
    stats["week"] = db.execute(
        "SELECT COUNT(*) AS n FROM bookings WHERE date BETWEEN ? AND ? "
        "AND status IN ('pending', 'confirmed', 'completed')",
        (week_start, today_s),
    ).fetchone()["n"]
    month_bookings = db.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(guests_count), 0) AS guests FROM bookings "
        "WHERE date BETWEEN ? AND ? AND status IN ('pending', 'confirmed', 'completed')",
        (month_start, today_s),
    ).fetchone()
    stats["month"] = month_bookings["n"]
    stats["month_guests"] = month_bookings["guests"]
    avg_check = int(get_settings().get("avg_check", "2400") or 2400)
    stats["revenue_estimate"] = month_bookings["n"] * avg_check
    stats["avg_check"] = avg_check
    stats["users"] = db.execute("SELECT COUNT(*) AS n FROM users WHERE role = 'guest'").fetchone()["n"]
    stats["reviews_pending"] = db.execute(
        "SELECT COUNT(*) AS n FROM reviews WHERE status = 'pending'"
    ).fetchone()["n"]
    stats["tables"] = db.execute("SELECT COUNT(*) AS n FROM dining_tables WHERE is_active = 1").fetchone()[
        "n"
    ]
    occupied = db.execute(
        "SELECT COALESCE(SUM((end_min - start_min) / 60.0), 0) AS hours FROM bookings "
        "WHERE date = ? AND status IN ('pending', 'confirmed')",
        (today_s,),
    ).fetchone()["hours"]
    capacity_hours = max(1, stats["tables"] * 10)
    stats["occupancy_today"] = min(100, round(occupied / capacity_hours * 100))
    stats["today_label"] = ru_date(today)
    return stats


def daily_counts(days: int = 14) -> list[dict]:
    db = get_db()
    today = date.today()
    start = today - timedelta(days=days - 1)
    rows = db.execute(
        "SELECT date, COUNT(*) AS n FROM bookings WHERE date BETWEEN ? AND ? "
        "AND status != 'cancelled' GROUP BY date",
        (start.isoformat(), today.isoformat()),
    ).fetchall()
    counts = {row["date"]: row["n"] for row in rows}
    values = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        values.append(
            {
                "date": day,
                "label": f"{day.day} {MONTH_LABEL[day.month - 1]}",
                "weekday": ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")[day.weekday()],
                "count": counts.get(day.isoformat(), 0),
            }
        )
    return values


def daily_chart(days: int = 14) -> dict:
    data = daily_counts(days)
    max_count = max([item["count"] for item in data] + [1])
    width, height = 760, 260
    left, right, top, bottom = 40, 14, 20, 38
    plot_w = width - left - right
    plot_h = height - top - bottom
    step = plot_w / len(data)
    bar_w = max(8, min(26, step * 0.55))
    bars = []
    for index, item in enumerate(data):
        bar_h = plot_h * item["count"] / max_count if item["count"] else 0
        bars.append(
            {
                "x": round(left + index * step + (step - bar_w) / 2, 1),
                "y": round(top + plot_h - bar_h, 1),
                "w": round(bar_w, 1),
                "h": round(bar_h, 1),
                "label": item["label"],
                "weekday": item["weekday"],
                "count": item["count"],
                "cx": round(left + index * step + step / 2, 1),
            }
        )
    grid = []
    for step_index in range(5):
        value = round(max_count * step_index / 4)
        y = top + plot_h - plot_h * step_index / 4
        grid.append({"y": round(y, 1), "label": value})
    return {
        "width": width,
        "height": height,
        "left": left,
        "right": right,
        "top": top,
        "bottom": bottom,
        "plot_h": plot_h,
        "bars": bars,
        "grid": grid,
    }


def hall_stats() -> list[dict]:
    db = get_db()
    month_start = date.today().replace(day=1).isoformat()
    rows = db.execute(
        "SELECT h.id, h.name, h.slug, h.capacity, "
        "COUNT(b.id) AS bookings, COALESCE(SUM(b.guests_count), 0) AS guests, "
        "COALESCE(SUM(CASE WHEN b.status IN ('confirmed', 'completed') THEN 1 ELSE 0 END), 0) AS confirmed "
        "FROM halls h LEFT JOIN bookings b ON b.hall_id = h.id AND b.date >= ? "
        "AND b.status IN ('pending', 'confirmed', 'completed') "
        "WHERE h.is_active = 1 GROUP BY h.id ORDER BY bookings DESC, h.sort_order",
        (month_start,),
    ).fetchall()
    result = [dict(row) for row in rows]
    max_bookings = max([item["bookings"] for item in result] + [1])
    for item in result:
        item["share"] = round(item["bookings"] / max_bookings * 100) if item["bookings"] else 0
    return result


def top_dishes(limit: int = 5) -> list:
    return (
        get_db()
        .execute(
            "SELECT d.name, d.slug, d.price, COUNT(f.user_id) AS favorites "
            "FROM dishes d LEFT JOIN favorites f ON f.dish_id = d.id "
            "WHERE d.is_active = 1 GROUP BY d.id ORDER BY favorites DESC, d.is_signature DESC LIMIT ?",
            (limit,),
        )
        .fetchall()
    )


def status_counts() -> dict:
    rows = get_db().execute("SELECT status, COUNT(*) AS n FROM bookings GROUP BY status").fetchall()
    base = {"pending": 0, "confirmed": 0, "cancelled": 0, "declined": 0, "completed": 0}
    base.update({row["status"]: row["n"] for row in rows})
    return base


def guest_insights(days: int = 90) -> dict:
    """Повторные гости и конверсия брони в визит за последние `days` дней."""
    db = get_db()
    since = (date.today() - timedelta(days=days)).isoformat()
    repeat = db.execute(
        "SELECT COUNT(*) AS n FROM (SELECT guest_phone FROM bookings "
        "WHERE date >= ? AND status IN ('confirmed', 'completed') AND guest_phone != '' "
        "GROUP BY guest_phone HAVING COUNT(*) >= 2)",
        (since,),
    ).fetchone()["n"]
    visitors = db.execute(
        "SELECT COUNT(*) AS n FROM bookings WHERE date >= ? AND status = 'completed'", (since,)
    ).fetchone()["n"]
    booked = db.execute(
        "SELECT COUNT(*) AS n FROM bookings WHERE date >= ? AND status != 'cancelled'", (since,)
    ).fetchone()["n"]
    conversion = round(visitors / booked * 100) if booked else 0
    return {
        "period_days": days,
        "repeat_guests": repeat,
        "visitors": visitors,
        "booked": booked,
        "conversion": conversion,
    }


def weekday_stats(weeks: int = 8) -> list[dict]:
    """Средний размер компании по дням недели за последние `weeks` недель."""
    db = get_db()
    since = (date.today() - timedelta(days=weeks * 7)).isoformat()
    rows = db.execute(
        "SELECT strftime('%w', date) AS weekday_num, COUNT(*) AS bookings, "
        "COALESCE(AVG(guests_count), 0) AS avg_guests, COALESCE(SUM(guests_count), 0) AS guests "
        "FROM bookings WHERE date >= ? AND status IN ('confirmed', 'completed') "
        "GROUP BY weekday_num",
        (since,),
    ).fetchall()
    by_num = {int(row["weekday_num"]): dict(row) for row in rows}
    weekdays = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
    # strftime: 0 = воскресенье; наш порядок — с понедельника.
    order = [1, 2, 3, 4, 5, 6, 0]
    max_avg = max([by_num.get(n, {}).get("avg_guests", 0) or 0 for n in order] + [1])
    result = []
    for index, num in enumerate(order):
        row = by_num.get(num)
        avg = round((row["avg_guests"] or 0), 1) if row else 0
        result.append(
            {
                "label": weekdays[index],
                "bookings": row["bookings"] if row else 0,
                "guests": row["guests"] if row else 0,
                "avg_guests": avg,
                "share": round(avg / max_avg * 100),
            }
        )
    return result


def hall_occupancy_month() -> list[dict]:
    """Заполненность залов за текущий месяц: бронь-часы относительно ёмкости."""
    db = get_db()
    month_start = date.today().replace(day=1)
    days_elapsed = (date.today() - month_start).days + 1
    halls = db.execute(
        "SELECT h.id, h.name FROM halls h WHERE h.is_active = 1 ORDER BY h.sort_order, h.name"
    ).fetchall()
    result = []
    for hall in halls:
        hours = db.execute(
            "SELECT COALESCE(SUM((end_min - start_min) / 60.0), 0) AS hours FROM bookings "
            "WHERE hall_id = ? AND date >= ? AND date <= ? AND status IN ('pending', 'confirmed', 'completed')",
            (hall["id"], month_start.isoformat(), date.today().isoformat()),
        ).fetchone()["hours"]
        tables = db.execute(
            "SELECT COUNT(*) AS n FROM dining_tables WHERE hall_id = ? AND is_active = 1", (hall["id"],)
        ).fetchone()["n"]
        capacity = max(1, tables * 10 * days_elapsed)
        result.append(
            {
                "name": hall["name"],
                "hours": round(hours),
                "capacity": capacity,
                "occupancy": min(100, round(hours / capacity * 100)),
            }
        )
    return result


def recent_audit(limit: int = 12) -> list:
    return (
        get_db()
        .execute(
            "SELECT a.*, u.name AS actor_name FROM audit_log a "
            "LEFT JOIN users u ON u.id = a.actor_id ORDER BY a.created_at DESC LIMIT ?",
            (limit,),
        )
        .fetchall()
    )


def export_bookings_csv() -> str:
    db = get_db()
    rows = db.execute(
        "SELECT b.code, b.date, b.time, b.end_min, b.status, b.guest_name, b.guest_phone, b.guest_email, "
        "b.guests_count, b.occasion, b.comment, b.created_at, h.name AS hall_name, t.name AS table_name "
        "FROM bookings b JOIN halls h ON h.id = b.hall_id JOIN dining_tables t ON t.id = b.table_id "
        "ORDER BY b.date DESC, b.time"
    ).fetchall()
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")
    writer.writerow(
        [
            "Код",
            "Дата",
            "Время",
            "Окончание",
            "Статус",
            "Гость",
            "Телефон",
            "Email",
            "Гостей",
            "Повод",
            "Комментарий",
            "Зал",
            "Стол",
            "Создана",
        ]
    )
    from services.bookings import time_from_minutes

    for row in rows:
        writer.writerow(
            [
                row["code"],
                row["date"],
                row["time"],
                time_from_minutes(row["end_min"]),
                row["status"],
                row["guest_name"],
                row["guest_phone"],
                row["guest_email"] or "",
                row["guests_count"],
                row["occasion"] or "",
                (row["comment"] or "").replace("\n", " "),
                row["hall_name"],
                row["table_name"],
                row["created_at"],
            ]
        )
    return output.getvalue()


def human_money(value) -> str:
    return money(value)


def generated_at() -> str:
    return utc_stamp()
