"""Личный кабинет гостя."""
from __future__ import annotations

import json

from flask import (
    Blueprint, Response, abort, flash, g, jsonify, redirect, render_template, request, url_for,
)
from werkzeug.utils import secure_filename

from core import login_required, request_wants_json, safe_next_url, utc_stamp
from services.bookings import (
    build_ics, change_status, get_booking, is_past, list_user_bookings, today_local,
    upcoming_for_user,
)
from services.menu import favorite_ids, favorites_for_user, toggle_favorite
from services.notifications import list_notifications, mark_all_read, mark_read, unread_count
from services.users import (
    change_password, delete_account, export_user_data, get_user, update_profile,
)

bp = Blueprint("account", __name__, url_prefix="/account")


@bp.before_request
def require_account():
    if g.get("user") is None:
        flash("Войдите в аккаунт, чтобы открыть кабинет.", "info")
        return redirect(url_for("auth.login", next=request.path))


@bp.get("/")
def dashboard():
    bookings = upcoming_for_user(g.user["id"], 4)
    notifications = list_notifications(g.user["id"], 5)
    favorites_count = len(favorites_for_user(g.user["id"]))
    history = list_user_bookings(g.user["id"], "history")[:4]
    return render_template(
        "account/dashboard.html",
        upcoming=bookings,
        notifications=notifications,
        favorites_count=favorites_count,
        history=history,
        unread=unread_count(g.user["id"]),
        page_title="Личный кабинет — ЧайHouse",
        meta_description="Брони, избранные блюда и настройки аккаунта ЧайHouse.",
        canonical=None,
    )


@bp.get("/bookings")
def bookings():
    scope = request.args.get("scope", "upcoming")
    if scope not in ("upcoming", "history", "all"):
        scope = "upcoming"
    status = request.args.get("status")
    items = list_user_bookings(g.user["id"], scope, status)
    return render_template(
        "account/bookings.html",
        bookings=items,
        scope=scope,
        active_status=status or "",
        page_title="Мои брони — ЧайHouse",
        meta_description="Активные и прошлые брони ЧайHouse.",
        canonical=None,
    )


@bp.get("/bookings/<code>")
def booking_detail(code: str):
    booking = get_booking(code)
    if not booking or booking["user_id"] != g.user["id"]:
        abort(404 if not booking else 403)
    can_cancel = booking["status"] in ("pending", "confirmed") and not is_past(booking)
    return render_template(
        "account/booking_detail.html",
        booking=booking,
        can_cancel=can_cancel,
        page_title=f"Бронь {booking['code']} — ЧайHouse",
        meta_description="Детали брони в чайхане ЧайHouse.",
        canonical=None,
    )


@bp.post("/bookings/<code>/cancel")
def cancel_booking(code: str):
    booking = get_booking(code)
    if not booking or booking["user_id"] != g.user["id"]:
        abort(404 if not booking else 403)
    ok, message = change_status(booking["id"], "cancelled", g.user, request.form.get("reason") or "")
    flash("Бронь отменена." if ok else message, "success" if ok else "danger")
    return redirect(url_for("account.booking_detail", code=code))


@bp.get("/bookings/<code>/calendar.ics")
def booking_ics(code: str):
    booking = get_booking(code)
    if not booking or booking["user_id"] != g.user["id"]:
        abort(404 if not booking else 403)
    response = Response(build_ics(booking), mimetype="text/calendar")
    response.headers["Content-Disposition"] = f'attachment; filename="chaihouse-{booking["code"]}.ics"'
    response.headers["Cache-Control"] = "private, no-store"
    return response


@bp.get("/favorites")
def favorites():
    items = favorites_for_user(g.user["id"])
    return render_template(
        "account/favorites.html",
        dishes=items,
        page_title="Избранные блюда — ЧайHouse",
        meta_description="Блюда ЧайHouse, которые вы сохранили.",
        canonical=None,
    )


@bp.post("/favorites/<int:dish_id>")
def favorite_toggle(dish_id: int):
    try:
        active, count = toggle_favorite(g.user["id"], dish_id)
    except ValueError as error:
        if request_wants_json():
            return jsonify({"ok": False, "error": str(error)}), 404
        flash(str(error), "danger")
        return redirect(url_for("public.menu"))
    if request_wants_json():
        return jsonify({"ok": True, "active": active, "count": count})
    flash("Блюдо добавлено в избранное." if active else "Блюдо убрано из избранного.", "success")
    next_url = safe_next_url(request.form.get("next"))
    return redirect(next_url or url_for("account.favorites"))


@bp.get("/notifications")
def notifications():
    items = list_notifications(g.user["id"])
    return render_template(
        "account/notifications.html",
        notifications=items,
        page_title="Уведомления — ЧайHouse",
        meta_description="Уведомления о бронированиях ЧайHouse.",
        canonical=None,
    )


@bp.post("/notifications/read-all")
def notifications_read_all():
    mark_all_read(g.user["id"])
    flash("Все уведомления отмечены прочитанными.", "success")
    return redirect(url_for("account.notifications"))


@bp.post("/notifications/<int:notification_id>/read")
def notification_read(notification_id: int):
    mark_read(notification_id, g.user["id"])
    return redirect(url_for("account.notifications"))


@bp.route("/settings", methods=["GET", "POST"])
def settings():
    errors = {}
    if request.method == "POST":
        errors = update_profile(g.user["id"], request.form)
        if not errors:
            flash("Профиль обновлён.", "success")
            return redirect(url_for("account.settings"))
    user = get_user(g.user["id"])
    return render_template(
        "account/settings.html",
        user=user,
        errors=errors,
        page_title="Настройки аккаунта — ЧайHouse",
        meta_description="Имя, телефон и email вашего аккаунта ЧайHouse.",
        canonical=None,
    )


@bp.post("/password")
def password():
    errors = change_password(
        g.user["id"],
        request.form.get("current") or "",
        request.form.get("password") or "",
        request.form.get("password2") or "",
    )
    if errors:
        for message in errors.values():
            flash(message, "danger")
        return redirect(url_for("account.settings") + "#password")
    from flask import session
    updated = get_user(g.user["id"])
    session["session_version"] = updated["session_version"]
    flash("Пароль изменён. Остальные сессии завершены.", "success")
    return redirect(url_for("account.settings") + "#password")


@bp.get("/export")
def export_data():
    payload = export_user_data(g.user["id"])
    response = Response(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        mimetype="application/json",
    )
    response.headers["Content-Disposition"] = 'attachment; filename="chaihouse-my-data.json"'
    response.headers["Cache-Control"] = "private, no-store"
    return response


@bp.route("/delete", methods=["GET", "POST"])
def delete():
    errors = {}
    if request.method == "POST":
        errors = delete_account(g.user["id"], request.form.get("password") or "")
        if not errors:
            from core import logout_user
            logout_user()
            flash("Аккаунт удалён. Персональные данные обезличены.", "success")
            return redirect(url_for("public.home"))
    return render_template(
        "account/delete.html",
        errors=errors,
        page_title="Удаление аккаунта — ЧайHouse",
        meta_description="Удаление аккаунта и обезличивание персональных данных.",
        canonical=None,
    )
