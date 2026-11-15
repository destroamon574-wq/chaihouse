"""Бронирование и календарь занятости."""
from __future__ import annotations

from datetime import date, timedelta

from flask import (
    Blueprint, Response, abort, current_app, flash, g, redirect, render_template, request, url_for,
)

from core import client_ip, get_settings, login_required, parse_iso_date, rate_limit
from services.bookings import (
    OCCASIONS, availability, build_ics, cancel_public, create_booking, get_booking,
    has_booking_access, is_past, month_calendar, remember_booking_access, slot_times,
    today_local,
)
from services.content import get_hall, get_hall_by_id, get_halls
from services.menu import signature_dishes
from services.users import find_by_email

bp = Blueprint("booking", __name__, url_prefix="/booking")


def _range_days() -> int:
    return int(current_app.config.get("BOOKING_DAYS_AHEAD", 90))


def _pick_date(raw: str | None) -> date:
    today = today_local()
    parsed = parse_iso_date(raw)
    if not parsed:
        return today
    if parsed < today:
        return today
    if parsed > today + timedelta(days=_range_days()):
        return today + timedelta(days=_range_days())
    return parsed


def _pick_hall(raw: str | None, halls: list[dict]) -> dict | None:
    if not halls:
        return None
    if raw:
        for hall in halls:
            if raw in (hall["slug"], str(hall["id"])):
                return hall
    return halls[0]


def _booking_context(form_data=None, errors=None):
    halls = get_halls()
    raw_hall = request.values.get("hall")
    selected_hall = _pick_hall(raw_hall, halls)
    selected_date = _pick_date(request.values.get("date"))
    if selected_hall is None:
        return {
            "halls": halls, "hall": None, "calendar": None, "availability": None,
            "selected_date": selected_date, "form_data": form_data or {}, "errors": errors or {},
            "occasions": OCCASIONS,
        }
    year, month = selected_date.year, selected_date.month
    calendar_data = month_calendar(selected_hall["id"], year, month)
    slots = availability(selected_hall["id"], selected_date)
    user = g.get("user")
    form_data = form_data or {}
    defaults = {
        "name": form_data.get("name") if form_data else (user["name"] if user else ""),
        "phone": form_data.get("phone") if form_data else (user["phone"] if user and user["phone"] else ""),
        "email": form_data.get("email") if form_data else (user["email"] if user else ""),
        "guests": form_data.get("guests") if form_data else "2",
        "occasion": form_data.get("occasion") if form_data else "",
        "comment": form_data.get("comment") if form_data else "",
    }
    selected_time = request.values.get("time", "")
    selected_table_id = None
    try:
        selected_table_id = int(request.values.get("table_id") or 0) or None
    except (TypeError, ValueError):
        selected_table_id = None
    slot = request.values.get("slot", "")
    if slot and "|" in slot:
        slot_table, slot_time = slot.split("|", 1)
        if slot_table.isdigit():
            selected_table_id = int(slot_table)
        selected_time = slot_time
    return {
        "halls": halls,
        "hall": selected_hall,
        "calendar": calendar_data,
        "availability": slots,
        "selected_date": selected_date,
        "selected_time": selected_time,
        "selected_table_id": selected_table_id,
        "form_data": defaults,
        "errors": errors or {},
        "occasions": OCCASIONS,
        "min_date": today_local().isoformat(),
        "max_date": (today_local() + timedelta(days=_range_days())).isoformat(),
        "today": today_local(),
    }


@bp.get("")
@login_required
def new():
    context = _booking_context()
    return render_template(
        "booking/new.html",
        **context,
        page_title="Бронирование стола — ЧайHouse",
        meta_description="Выберите зал, дату и время, забронируйте стол в ЧайHouse онлайн. "
                         "Подтвердим бронь в течение 15 минут.",
        canonical=current_app.config["SITE_URL"].rstrip("/") + "/booking",
    )


@bp.post("")
@login_required
def create():
    allowed, _ = rate_limit(f"booking:{client_ip()}", 12, 3600)
    data = request.form.to_dict(flat=True)
    slot = data.get("slot", "")
    if slot and "|" in slot:
        slot_table, slot_time = slot.split("|", 1)
        if slot_table.isdigit():
            data["table_id"] = int(slot_table)
        data["time"] = slot_time
    context = _booking_context(form_data=data, errors={})
    if not allowed:
        flash("Слишком много заявок за короткое время. Позвоните нам или попробуйте позже.", "danger")
        context["errors"] = {"_": "Слишком много заявок. Попробуйте позже или позвоните по телефону."}
        return render_template(
            "booking/new.html", **context,
            page_title="Бронирование стола — ЧайHouse",
            meta_description="Бронирование стола в ЧайHouse.",
            canonical=current_app.config["SITE_URL"].rstrip("/") + "/booking",
        ), 429
    user = g.get("user")
    booking, errors = create_booking(data, user["id"] if user else None)
    if booking:
        flash("Заявка принята! Подтвердим бронь по телефону в течение 15 минут.", "success")
        return redirect(url_for("booking.success", code=booking["code"]))
    context["errors"] = errors
    return render_template(
        "booking/new.html", **context,
        page_title="Бронирование стола — ЧайHouse",
        meta_description="Бронирование стола в ЧайHouse.",
        canonical=current_app.config["SITE_URL"].rstrip("/") + "/booking",
    ), 422


@bp.get("/success/<code>")
def success(code: str):
    booking = get_booking(code)
    if not booking or not has_booking_access(booking):
        abort(404)
    can_cancel = booking["status"] in ("pending", "confirmed") and not is_past(booking)
    return render_template(
        "booking/success.html",
        booking=booking,
        can_cancel=can_cancel,
        page_title=f"Бронь {booking['code']} — ЧайHouse",
        meta_description="Ваша бронь в чайхане ЧайHouse.",
        canonical=None,
    )


@bp.post("/<code>/cancel")
def cancel(code: str):
    ok, message = cancel_public(code, request.form.get("reason") or "")
    if ok:
        flash("Бронь отменена. Если планы изменятся — будем рады видеть вас снова.", "success")
    else:
        flash(message, "danger")
    booking = get_booking(code)
    if booking and has_booking_access(booking):
        return redirect(url_for("booking.success", code=code))
    return redirect(url_for("public.home"))


@bp.get("/<code>/calendar.ics")
def calendar(code: str):
    booking = get_booking(code)
    if not booking or not has_booking_access(booking):
        abort(404)
    response = Response(build_ics(booking), mimetype="text/calendar")
    response.headers["Content-Disposition"] = f'attachment; filename="chaihouse-{booking["code"]}.ics"'
    response.headers["Cache-Control"] = "private, no-store"
    return response


@bp.route("/lookup", methods=["GET", "POST"])
def lookup():
    error = None
    code = ""
    if request.method == "POST":
        allowed, _ = rate_limit(f"lookup:{client_ip()}", 10, 900)
        code = (request.form.get("code") or "").strip().upper()[:20]
        from core import normalize_phone
        phone = normalize_phone(request.form.get("phone") or "")
        if not allowed:
            error = "Слишком много попыток. Попробуйте позже."
        else:
            booking = get_booking(code)
            if booking and phone and booking["guest_phone"] == phone:
                remember_booking_access(booking["code"])
                return redirect(url_for("booking.success", code=booking["code"]))
            error = "Бронь с таким кодом и телефоном не найдена. Проверьте данные."
    return render_template(
        "booking/lookup.html",
        error=error,
        code=code,
        page_title="Найти бронь — ЧайHouse",
        meta_description="Найдите бронь ЧайHouse по коду и номеру телефона.",
        canonical=current_app.config["SITE_URL"].rstrip("/") + "/booking/lookup",
    )
