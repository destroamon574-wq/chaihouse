"""Админ-панель: брони, меню, залы, галерея, отзывы, журнал."""

from __future__ import annotations

import json
from datetime import timedelta

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from core import (
    get_settings,
    parse_iso_date,
    safe_next_url,
)
from services.analytics import overview, recent_audit, status_counts
from services.audit import log_action
from services.bookings import (
    ADMIN_TRANSITIONS,
    admin_week_grid,
    change_status,
    get_booking_by_id,
    list_all_bookings,
    today_local,
)
from services.content import (
    GALLERY_CATEGORIES,
    PRESET_IMAGES,
    add_gallery,
    add_table,
    delete_gallery,
    get_gallery,
    get_hall_by_id,
    get_halls,
    get_tables_admin,
    list_reviews,
    moderate_review,
    toggle_hall,
    toggle_table,
    update_hall,
)
from services.menu import (
    admin_dishes,
    create_dish,
    delete_dish,
    get_dish_by_id,
    list_categories,
    toggle_dish_active,
    update_dish,
)
from services.uploads import UploadError, save_image

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
def require_staff():
    if g.get("user") is None:
        flash("Войдите как администратор.", "info")
        return redirect(url_for("auth.login", next=request.path))
    if g.user["role"] not in ("admin", "owner"):
        abort(403)


def _nav_context() -> dict:
    return {"settings_data": get_settings()}


@bp.get("/")
def dashboard():
    pending, _ = list_all_bookings(status="pending", page=1)
    today_bookings = list_all_bookings(date_value=today_local().isoformat(), page=1)[0]
    reviews, _ = list_reviews("pending", 1, 5)
    return render_template(
        "admin/dashboard.html",
        stats=overview(),
        pending=pending[:5],
        today_bookings=today_bookings,
        reviews=reviews,
        audit=recent_audit(8),
        status_counts=status_counts(),
        page_title="Админ-панель — ЧайHouse",
        meta_description="Управление бронями и контентом ЧайHouse.",
        canonical=None,
        **_nav_context(),
    )


@bp.get("/bookings")
def bookings():
    status = request.args.get("status") or ""
    date_value = request.args.get("date") or ""
    q = request.args.get("q") or ""
    items, pages = list_all_bookings(
        status=status, date_value=date_value, q=q, page=request.args.get("page", 1)
    )
    return render_template(
        "admin/bookings.html",
        bookings=items,
        pages=pages,
        status=status,
        date_value=date_value,
        q=q,
        page_title="Брони — админ-панель",
        meta_description="Все брони ЧайHouse.",
        canonical=None,
        **_nav_context(),
    )


@bp.get("/bookings/<int:booking_id>")
def booking_detail(booking_id: int):
    booking = get_booking_by_id(booking_id)
    if not booking:
        abort(404)
    return render_template(
        "admin/booking_detail.html",
        booking=booking,
        allowed_statuses=sorted(ADMIN_TRANSITIONS.get(booking["status"], set())),
        page_title=f"Бронь {booking['code']} — админ-панель",
        meta_description="Детали брони.",
        canonical=None,
        **_nav_context(),
    )


@bp.post("/bookings/<int:booking_id>/status")
def booking_status(booking_id: int):
    new_status = request.form.get("status") or ""
    ok, message = change_status(booking_id, new_status, g.user, request.form.get("reason") or "")
    labels = {
        "pending": "ожидает",
        "confirmed": "подтверждена",
        "cancelled": "отменена",
        "declined": "отклонена",
        "completed": "завершена",
    }
    flash(
        f"Статус изменён на «{labels.get(new_status, new_status)}»." if ok else message,
        "success" if ok else "danger",
    )
    next_url = safe_next_url(request.form.get("next"))
    return redirect(next_url or url_for("admin.booking_detail", booking_id=booking_id))


@bp.get("/calendar")
def calendar():
    raw = request.args.get("date") or ""
    start = parse_iso_date(raw)
    today = today_local()
    if not start:
        start = today - timedelta(days=today.weekday())
    elif start.weekday() != 0:
        start -= timedelta(days=start.weekday())
    if start > today:
        start = today - timedelta(days=today.weekday())
    grid = admin_week_grid(start)
    return render_template(
        "admin/calendar.html",
        grid=grid,
        page_title="Календарь загрузки — админ-панель",
        meta_description="Загрузка залов на неделю.",
        canonical=None,
        **_nav_context(),
    )


@bp.get("/menu")
def menu():
    q = (request.args.get("q") or "").strip().lower()
    dishes = admin_dishes()
    if q:
        dishes = [dish for dish in dishes if q in dish["name"].lower() or q in dish["slug"]]
    return render_template(
        "admin/menu.html",
        dishes=dishes,
        categories=list_categories(),
        q=q,
        page_title="Меню — админ-панель",
        meta_description="Управление меню ЧайHouse.",
        canonical=None,
        **_nav_context(),
    )


def _image_path_from_form(form, prefix: str, current: str | None = None) -> tuple[str | None, str | None]:
    upload = request.files.get("image_file") or form.get("image_file")
    if upload is not None and getattr(upload, "filename", ""):
        try:
            return save_image(upload, prefix), None
        except UploadError as error:
            return None, str(error)
    preset = (form.get("image_preset") or "").strip()
    if preset:
        if preset.startswith("img/") and ".." not in preset and preset.endswith(".svg"):
            return preset, None
        if preset.startswith("uploads/") and ".." not in preset:
            return preset, None
        return None, "Недопустимый путь к изображению."
    if current:
        return current, None
    return None, "Выберите изображение или загрузите файл."


@bp.route("/menu/new", methods=["GET", "POST"])
def menu_new():
    errors = {}
    if request.method == "POST":
        image_path, image_error = _image_path_from_form(request.form, "dish")
        if image_error:
            errors["image"] = image_error
        else:
            dish_id, errors = create_dish(request.form, image_path)
            if dish_id:
                log_action("dish.created", "dish", dish_id, {"name": request.form.get("name")})
                from database import get_db

                get_db().commit()
                flash("Блюдо добавлено в меню.", "success")
                return redirect(url_for("admin.menu"))
    return render_template(
        "admin/dish_form.html",
        dish=None,
        errors=errors,
        categories=list_categories(),
        presets=PRESET_IMAGES,
        page_title="Новое блюдо — админ-панель",
        meta_description="Добавление блюда.",
        canonical=None,
        **_nav_context(),
    )


@bp.route("/menu/<int:dish_id>/edit", methods=["GET", "POST"])
def menu_edit(dish_id: int):
    dish = get_dish_by_id(dish_id)
    if not dish:
        abort(404)
    errors = {}
    if request.method == "POST":
        image_path, image_error = _image_path_from_form(request.form, "dish", dish["image"])
        if image_error:
            errors["image"] = image_error
        else:
            errors = update_dish(dish_id, request.form, image_path)
            if not errors:
                log_action("dish.updated", "dish", dish_id, {"name": request.form.get("name")})
                from database import get_db

                get_db().commit()
                flash("Блюдо обновлено.", "success")
                return redirect(url_for("admin.menu"))
    return render_template(
        "admin/dish_form.html",
        dish=dish,
        errors=errors,
        categories=list_categories(),
        presets=PRESET_IMAGES,
        page_title="Редактирование блюда — админ-панель",
        meta_description="Редактирование блюда.",
        canonical=None,
        **_nav_context(),
    )


@bp.post("/menu/<int:dish_id>/toggle")
def menu_toggle(dish_id: int):
    try:
        active = toggle_dish_active(dish_id)
    except ValueError as error:
        flash(str(error), "danger")
    else:
        flash("Блюдо снова в меню." if active else "Блюдо скрыто из меню.", "success")
        log_action("dish.toggled", "dish", dish_id, {"is_active": active})
        from database import get_db

        get_db().commit()
    return redirect(url_for("admin.menu"))


@bp.post("/menu/<int:dish_id>/delete")
def menu_delete(dish_id: int):
    dish = get_dish_by_id(dish_id)
    if not dish:
        abort(404)
    delete_dish(dish_id)
    log_action("dish.deleted", "dish", dish_id, {"name": dish["name"]})
    from database import get_db

    get_db().commit()
    flash("Блюдо удалено из меню.", "success")
    return redirect(url_for("admin.menu"))


@bp.get("/halls")
def halls():
    return render_template(
        "admin/halls.html",
        halls=get_halls(include_inactive=True),
        tables=get_tables_admin(),
        page_title="Залы — админ-панель",
        meta_description="Управление залами и столами.",
        canonical=None,
        **_nav_context(),
    )


@bp.route("/halls/<int:hall_id>/edit", methods=["GET", "POST"])
def hall_edit(hall_id: int):
    hall = get_hall_by_id(hall_id)
    if not hall:
        abort(404)
    errors = {}
    if request.method == "POST":
        image_path, image_error = _image_path_from_form(request.form, "hall", hall["image"])
        if image_error:
            errors["image"] = image_error
        else:
            errors = update_hall(hall_id, request.form, image_path)
            if not errors:
                flash("Зал обновлён.", "success")
                return redirect(url_for("admin.halls"))
    return render_template(
        "admin/hall_form.html",
        hall=hall,
        features_text="\n".join(json.loads(hall["features"] or "[]")),
        errors=errors,
        presets=PRESET_IMAGES,
        page_title="Редактирование зала — админ-панель",
        meta_description="Редактирование зала.",
        canonical=None,
        **_nav_context(),
    )


@bp.post("/halls/<int:hall_id>/toggle")
def hall_toggle(hall_id: int):
    try:
        active = toggle_hall(hall_id)
    except ValueError as error:
        flash(str(error), "danger")
    else:
        flash("Зал открыт для бронирования." if active else "Зал скрыт с сайта.", "success")
    return redirect(url_for("admin.halls"))


@bp.post("/halls/<int:hall_id>/tables")
def table_add(hall_id: int):
    _, errors = add_table(hall_id, request.form)
    if errors:
        for message in errors.values():
            flash(message, "danger")
    else:
        flash("Стол добавлен.", "success")
    return redirect(url_for("admin.halls"))


@bp.post("/tables/<int:table_id>/toggle")
def table_toggle(table_id: int):
    try:
        active = toggle_table(table_id)
    except ValueError as error:
        flash(str(error), "danger")
    else:
        flash("Стол активен." if active else "Стол выключен из бронирования.", "success")
    return redirect(url_for("admin.halls"))


@bp.route("/gallery", methods=["GET", "POST"])
def gallery():
    errors = {}
    if request.method == "POST":
        image_path, image_error = _image_path_from_form(request.form, "gallery")
        if image_error:
            errors["image"] = image_error
        else:
            image_id, errors = add_gallery(request.form, image_path)
            if image_id:
                flash("Фотография добавлена в галерею.", "success")
                return redirect(url_for("admin.gallery"))
    category = request.args.get("category") or ""
    return render_template(
        "admin/gallery.html",
        images=get_gallery(category if category in GALLERY_CATEGORIES else None, include_inactive=True),
        categories=GALLERY_CATEGORIES,
        active_category=category,
        presets=PRESET_IMAGES,
        errors=errors,
        page_title="Галерея — админ-панель",
        meta_description="Управление галереей.",
        canonical=None,
        **_nav_context(),
    )


@bp.post("/gallery/<int:image_id>/delete")
def gallery_delete(image_id: int):
    delete_gallery(image_id)
    flash("Фотография удалена.", "success")
    return redirect(url_for("admin.gallery"))


@bp.get("/reviews")
def reviews():
    status = request.args.get("status", "pending")
    items, pages = list_reviews(status, request.args.get("page", 1), 10)
    return render_template(
        "admin/reviews.html",
        reviews=items,
        pages=pages,
        status=status,
        page_title="Отзывы — админ-панель",
        meta_description="Модерация отзывов.",
        canonical=None,
        **_nav_context(),
    )


@bp.post("/reviews/<int:review_id>/moderate")
def review_moderate(review_id: int):
    action = request.form.get("action") or ""
    ok, message = moderate_review(review_id, action, request.form.get("reply") or "")
    flash("Отзыв обновлён." if ok else message, "success" if ok else "danger")
    next_url = safe_next_url(request.form.get("next"))
    return redirect(next_url or url_for("admin.reviews"))


@bp.get("/audit")
def audit():
    from database import get_db

    rows = (
        get_db()
        .execute(
            "SELECT a.*, u.name AS actor_name FROM audit_log a LEFT JOIN users u ON u.id = a.actor_id "
            "ORDER BY a.created_at DESC LIMIT 200"
        )
        .fetchall()
    )
    return render_template(
        "admin/audit.html",
        entries=rows,
        page_title="Журнал действий — админ-панель",
        meta_description="Журнал критичных действий.",
        canonical=None,
        **_nav_context(),
    )
