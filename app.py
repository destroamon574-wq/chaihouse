"""Точка входа приложения «ЧайHouse»."""
from __future__ import annotations

import secrets
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request

from core import (
    Config, guests_label, inject_globals, load_logged_in_user, money, month_title, pretty_phone,
    query_url, request_wants_json, ru_date, ru_datetime, status_meta, utc_now, validate_csrf,
)
from database import init_app as init_database, init_db
from services.notifications import unread_count
from services.uploads import image_url


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)

    init_database(app)

    from blueprints.account import bp as account_bp
    from blueprints.admin import bp as admin_bp
    from blueprints.api import bp as api_bp
    from blueprints.auth import bp as auth_bp
    from blueprints.booking import bp as booking_bp
    from blueprints.owner import bp as owner_bp
    from blueprints.public import bp as public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(owner_bp)

    app.before_request(load_logged_in_user)
    app.before_request(_csrf_protection)
    app.after_request(_security_headers)
    app.context_processor(_context)

    app.jinja_env.filters["money"] = money
    app.jinja_env.filters["ru_date"] = ru_date
    app.jinja_env.filters["ru_datetime"] = ru_datetime
    app.jinja_env.filters["pretty_phone"] = pretty_phone
    app.jinja_env.filters["guests"] = guests_label
    app.jinja_env.globals["image_url"] = image_url
    app.jinja_env.globals["status_meta"] = status_meta
    app.jinja_env.globals["query_url"] = query_url
    app.jinja_env.globals["utc_now"] = utc_now
    app.jinja_env.globals["month_title"] = month_title

    @app.errorhandler(400)
    def bad_request(error):
        if request_wants_json():
            return jsonify({"ok": False, "error": getattr(error, "description", "Некорректный запрос.")}), 400
        return render_template("errors/400.html", error=error), 400

    @app.errorhandler(403)
    def forbidden(_error):
        if request_wants_json():
            return jsonify({"ok": False, "error": "Доступ запрещён."}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        if request_wants_json():
            return jsonify({"ok": False, "error": "Страница не найдена."}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        if request_wants_json():
            return jsonify({"ok": False, "error": "Метод не поддерживается."}), 405
        return render_template("errors/405.html"), 405

    @app.errorhandler(413)
    def too_large(_error):
        if request_wants_json():
            return jsonify({"ok": False, "error": "Файл слишком большой (максимум 3 МБ)."}), 413
        return render_template("errors/413.html"), 413

    @app.errorhandler(429)
    def too_many(_error):
        if request_wants_json():
            return jsonify({"ok": False, "error": "Слишком много попыток. Попробуйте позже."}), 429
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def server_error(_error):
        if request_wants_json():
            return jsonify({"ok": False, "error": "Внутренняя ошибка сервера."}), 500
        return render_template("errors/500.html"), 500

    with app.app_context():
        init_db()

    return app


def _csrf_protection():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        validate_csrf()


def _context() -> dict:
    context = inject_globals()
    user = g.get("user")
    context["unread_notifications"] = unread_count(user["id"]) if user else 0
    context["body_class"] = ""
    # Nonce для inline-скриптов (Tailwind-конфиг): каждый запрос — новый nonce.
    if "script_nonce" not in g:
        g.script_nonce = secrets.token_urlsafe(16)
    context["script_nonce"] = g.script_nonce
    return context


def _security_headers(response):
    nonce = g.get("script_nonce", "")
    nonce_part = f" 'nonce-{nonce}'" if nonce else ""
    csp = (
        "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        f"script-src 'self'{nonce_part} 'unsafe-eval' https://cdn.tailwindcss.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self'; form-action 'self'; manifest-src 'self'"
    )
    response.headers.setdefault("Content-Security-Policy", csp)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(self), camera=(), microphone=(), payment=()"
    )
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    if g.get("user"):
        response.headers.setdefault("Cache-Control", "private, no-store")
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


if __name__ == "__main__":
    create_app().run(debug=True)
