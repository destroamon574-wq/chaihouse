"""Кабинет владельца: аналитика, роли, цены и настройки."""
from __future__ import annotations

from datetime import date

from flask import (
    Blueprint, Response, abort, flash, g, redirect, render_template, request, url_for,
)

from core import get_settings, owner_required, safe_next_url
from services.analytics import (
    daily_chart, export_bookings_csv, guest_insights, hall_occupancy_month, hall_stats, overview,
    recent_audit, status_counts, top_dishes, weekday_stats,
)
from services.content import update_settings
from services.users import list_users, set_user_role, user_stats

bp = Blueprint("owner", __name__, url_prefix="/owner")


@bp.before_request
@owner_required
def require_owner():
    return None


@bp.get("/")
def dashboard():
    return render_template(
        "owner/dashboard.html",
        stats=overview(),
        chart=daily_chart(14),
        halls=hall_stats(),
        dishes=top_dishes(5),
        statuses=status_counts(),
        users=user_stats(),
        audit=recent_audit(10),
        insights=guest_insights(),
        weekdays=weekday_stats(),
        occupancy=hall_occupancy_month(),
        page_title="Аналитика — ЧайHouse",
        meta_description="Показатели ресторана ЧайHouse.",
        canonical=None,
        settings_data=get_settings(),
    )


@bp.get("/users")
def users():
    q = request.args.get("q") or ""
    role = request.args.get("role") or ""
    return render_template(
        "owner/users.html",
        users=list_users(q, role),
        q=q,
        role=role,
        stats=user_stats(),
        page_title="Пользователи — ЧайHouse",
        meta_description="Роли и доступы пользователей.",
        canonical=None,
        settings_data=get_settings(),
    )


@bp.post("/users/<int:user_id>/role")
def user_role(user_id: int):
    role = request.form.get("role") or ""
    errors = set_user_role(g.user, user_id, role)
    if errors:
        for message in errors.values():
            flash(message, "danger")
    else:
        flash("Роль пользователя обновлена.", "success")
    next_url = safe_next_url(request.form.get("next"))
    return redirect(next_url or url_for("owner.users"))


@bp.route("/settings", methods=["GET", "POST"])
def settings():
    errors = {}
    if request.method == "POST":
        errors = update_settings(request.form)
        if not errors:
            flash("Настройки заведения обновлены.", "success")
            return redirect(url_for("owner.settings"))
    return render_template(
        "owner/settings.html",
        form=request.form if request.method == "POST" else get_settings(),
        errors=errors,
        page_title="Настройки заведения — ЧайHouse",
        meta_description="Контакты, часы работы и параметры бронирования.",
        canonical=None,
        settings_data=get_settings(),
    )


@bp.get("/export.csv")
def export_csv():
    csv_data = export_bookings_csv()
    response = Response(csv_data, mimetype="text/csv")
    response.headers["Content-Disposition"] = f'attachment; filename="chaihouse-bookings-{date.today().isoformat()}.csv"'
    response.headers["Cache-Control"] = "private, no-store"
    return response


@bp.post("/backup")
def backup():
    from services.audit import log_action
    from services.backup import create_backup

    target, kept = create_backup()
    log_action("backup.created", "backup", target.name, {"copies": kept})
    from database import get_db

    get_db().commit()
    flash(f"Резервная копия создана: {target.name}. Всего копий: {kept}.", "success")
    return redirect(url_for("owner.dashboard"))
