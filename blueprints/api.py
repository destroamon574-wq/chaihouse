"""Публичный JSON API занятости."""

from __future__ import annotations


from flask import Blueprint, jsonify, request

from core import client_ip, parse_iso_date, rate_limit
from services.bookings import availability, month_calendar, today_local
from services.content import get_hall_by_id

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/availability")
def availability_api():
    allowed, retry = rate_limit(f"api-avail:{client_ip()}", 120, 60)
    if not allowed:
        return jsonify({"ok": False, "error": "Слишком много запросов.", "retry_after": retry}), 429
    hall_id = request.args.get("hall_id", type=int)
    hall = get_hall_by_id(hall_id) if hall_id else None
    if not hall or not hall["is_active"]:
        return jsonify({"ok": False, "error": "Зал не найден."}), 404
    day = parse_iso_date(request.args.get("date"))
    if not day:
        return jsonify({"ok": False, "error": "Укажите корректную дату."}), 400
    today = today_local()
    if day < today or (day - today).days > 90:
        return jsonify({"ok": False, "error": "Дата вне периода бронирования."}), 400
    data = availability(hall_id, day)
    return jsonify(
        {
            "ok": True,
            "hall": {"id": hall["id"], "name": hall["name"], "slug": hall["slug"]},
            "date": day.isoformat(),
            "slots": data["slots"],
            "bookings_count": data["bookings_count"],
            "tables": [
                {
                    "id": row["table"]["id"],
                    "name": row["table"]["name"],
                    "seats": row["table"]["seats"],
                    "cells": [
                        {
                            "time": cell["time"],
                            "end": cell["end"],
                            "free": cell["free"],
                            "past": cell["past"],
                            "status": cell["booking"]["status"] if cell["booking"] else None,
                        }
                        for cell in row["cells"]
                    ],
                }
                for row in data["grid"]
            ],
        }
    )


@bp.get("/calendar")
def calendar_api():
    allowed, retry = rate_limit(f"api-cal:{client_ip()}", 60, 60)
    if not allowed:
        return jsonify({"ok": False, "error": "Слишком много запросов.", "retry_after": retry}), 429
    hall_id = request.args.get("hall_id", type=int)
    hall = get_hall_by_id(hall_id) if hall_id else None
    if not hall or not hall["is_active"]:
        return jsonify({"ok": False, "error": "Зал не найден."}), 404
    try:
        year = int(request.args.get("year", ""))
        month = int(request.args.get("month", ""))
        if not (1 <= month <= 12) or not (2000 <= year <= 2100):
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Укажите год и месяц."}), 400
    data = month_calendar(hall_id, year, month)
    return jsonify(
        {
            "ok": True,
            "year": year,
            "month": month,
            "prev": data["prev"],
            "next": data["next"],
            "weeks": [
                [
                    None
                    if day is None
                    else {
                        "date": day["date"].isoformat(),
                        "day": day["day"],
                        "count": day["count"],
                        "level": day["level"],
                        "past": day["past"],
                        "today": day["today"],
                        "bookable": day["bookable"],
                    }
                    for day in week
                ]
                for week in data["weeks"]
            ],
        }
    )
