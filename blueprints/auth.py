"""Регистрация, вход, выход и восстановление пароля."""

from __future__ import annotations

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from core import (
    client_ip,
    login_user,
    logout_user,
    rate_limit,
    safe_next_url,
)
from services.audit import log_action
from services.users import (
    authenticate,
    create_user,
    find_reset,
    request_password_reset,
    reset_password as perform_password_reset,
)

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.get("user"):
        return redirect(url_for("account.dashboard"))
    next_url = safe_next_url(request.values.get("next"))
    if request.method == "POST":
        allowed, retry = rate_limit(f"login-ip:{client_ip()}", 12, 300)
        email = (request.form.get("email") or "").strip().lower()[:254]
        allowed_email, retry_email = rate_limit(f"login-email:{client_ip()}:{email}", 5, 300)
        if not allowed or not allowed_email:
            flash("Слишком много попыток входа. Подождите несколько минут и попробуйте снова.", "danger")
            return render_template("auth/login.html", email=email, next_url=next_url), 429
        password = request.form.get("password") or ""
        user = authenticate(email, password)
        if not user:
            flash("Неверный email или пароль.", "danger")
            return render_template("auth/login.html", email=email, next_url=next_url), 401
        login_user(user)
        log_action("auth.login", "user", user["id"])
        from database import get_db

        get_db().commit()
        flash(f"Здравствуйте, {user['name'].split()[0]}!", "success")
        return redirect(next_url or url_for("account.dashboard"))
    return render_template("auth/login.html", next_url=next_url)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.get("user"):
        return redirect(url_for("account.dashboard"))
    next_url = safe_next_url(request.values.get("next"))
    form_data = {}
    errors = {}
    if request.method == "POST":
        allowed, _ = rate_limit(f"register:{client_ip()}", 5, 3600)
        if not allowed:
            flash("Слишком много попыток регистрации. Попробуйте позже.", "danger")
            return render_template(
                "auth/register.html", form_data=request.form, errors={}, next_url=next_url
            ), 429
        user_id, errors = create_user(request.form)
        if user_id:
            from services.users import get_user

            user = get_user(user_id)
            login_user(user)
            flash("Аккаунт создан. Добро пожаловать в ЧайHouse!", "success")
            return redirect(next_url or url_for("account.dashboard"))
        form_data = request.form
    return render_template("auth/register.html", form_data=form_data, errors=errors, next_url=next_url)


@bp.post("/logout")
def logout():
    if g.get("user"):
        log_action("auth.logout", "user", g.user["id"])
        from database import get_db

        get_db().commit()
    logout_user()
    flash("Вы вышли из аккаунта.", "info")
    return redirect(url_for("public.home"))


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    reset_url = None
    email = ""
    if request.method == "POST":
        allowed, _ = rate_limit(f"reset:{client_ip()}", 4, 900)
        email = (request.form.get("email") or "").strip().lower()[:254]
        if not allowed:
            flash("Слишком много запросов. Попробуйте позже.", "danger")
        else:
            token = request_password_reset(email)
            if token and current_app.config.get("DEMO_MODE", True):
                reset_url = url_for("auth.reset_password", token=token, _external=False)
            flash("Если аккаунт с таким email существует, мы отправили ссылку для восстановления.", "info")
    return render_template("auth/forgot.html", email=email, reset_url=reset_url)


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    row = find_reset(token)
    if not row:
        return render_template("auth/reset.html", invalid=True, token=token, errors={}), 400
    errors = {}
    if request.method == "POST":
        allowed, _ = rate_limit(f"reset-submit:{client_ip()}", 6, 900)
        if not allowed:
            flash("Слишком много попыток. Попробуйте позже.", "danger")
            return render_template("auth/reset.html", invalid=False, token=token, errors={}), 429
        user_id, errors = perform_password_reset(
            token, request.form.get("password") or "", request.form.get("password2") or ""
        )
        if user_id:
            logout_user()
            flash("Пароль обновлён. Войдите с новым паролем.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/reset.html", invalid=False, token=token, errors=errors)
