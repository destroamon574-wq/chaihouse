"""Общие настройки, безопасность и помощники приложения."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from flask import abort, current_app, flash, g, jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv() -> None:
    """Минимальная поддержка .env без внешних зависимостей."""
    path = BASE_DIR / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me-chaihouse")
    DATABASE_PATH = os.environ.get("DATABASE_PATH", str(BASE_DIR / "instance" / "chaihouse.db"))
    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", str(BASE_DIR / "instance" / "uploads"))
    SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:5000").rstrip("/")
    DEMO_MODE = _env_bool("DEMO_MODE", True)
    PRODUCTION = os.environ.get("FLASK_ENV", "development").lower() == "production"

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = PRODUCTION
    PERMANENT_SESSION_LIFETIME = timedelta(days=14)
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024
    AUTO_SEED = True

    WTF_CSRF_TIME_LIMIT = None
    TIMEZONE_LABEL = "МСК"
    BOOKING_DAYS_AHEAD = 90
    BOOKING_DURATION_MIN = 120
    SLOT_START_HOUR = 12
    SLOT_END_HOUR = 22


DEFAULT_SETTINGS = {
    "restaurant_name": "ЧайHouse",
    "tagline": "Восточная кухня, чай и неспешные вечера",
    "phone": "+7 (495) 120-48-18",
    "email": "hello@chaihouse.example",
    "address": "Москва, Ходынский бульвар, 4, ТРЦ «Авиапарк», 3 этаж",
    "address_short": "Ходынский бульвар, 4 · Авиапарк",
    "hours": "Ежедневно 12:00–00:00",
    "lat": "55.790622",
    "lng": "37.532186",
    "avg_check": "2400",
    "max_guests": "20",
    "booking_note": "Подтверждаем бронь в течение 15 минут в рабочее время.",
    "legal_name": "ООО «ЧайHouse»",
    "privacy_email": "privacy@chaihouse.example",
    "telegram_bot_token": "",
    "telegram_chat_id": "",
}

BOOKING_STATUSES = {
    "pending": ("Ожидает подтверждения", "warning"),
    "confirmed": ("Подтверждена", "success"),
    "cancelled": ("Отменена", "muted"),
    "declined": ("Отклонена", "danger"),
    "completed": ("Завершена", "info"),
}
ROLE_LABELS = {"guest": "Гость", "admin": "Администратор", "owner": "Владелец"}
MONTHS_GENITIVE = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)
MONTHS_NOMINATIVE = (
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)
WEEKDAYS_SHORT = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")

PHONE_RE = re.compile(r"^\+?\d{10,15}$")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s.]+(\.[^@\s.]+)+$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,80}$")
COMMON_PASSWORDS = {
    "12345678", "123456789", "password", "qwerty123", "11111111",
    "password1", "admin123", "letmein1", "chaihouse", "qwertyui",
}


# ---------------------------------------------------------------------------
# Время и форматирование
# ---------------------------------------------------------------------------

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_stamp() -> str:
    return utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_stamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def ru_date(value, style: str = "long") -> str:
    """Форматирует date/строку по-русски: 5 ноября 2026."""
    if isinstance(value, str):
        parsed = parse_iso_date(value[:10])
    elif isinstance(value, datetime):
        parsed = value.date()
    else:
        parsed = value
    if not parsed:
        return ""
    if style == "short":
        return f"{parsed.day:02d}.{parsed.month:02d}.{parsed.year}"
    if style == "day":
        return f"{parsed.day} {MONTHS_GENITIVE[parsed.month - 1]}"
    return f"{parsed.day} {MONTHS_GENITIVE[parsed.month - 1]} {parsed.year}"


def ru_datetime(value: str | None, style: str = "short") -> str:
    parsed = parse_stamp(value)
    if not parsed:
        return "—"
    local = parsed + timedelta(hours=3)
    if style == "time":
        return local.strftime("%H:%M")
    return f"{ru_date(local.date(), 'short')} · {local.strftime('%H:%M')}"


def month_title(year: int, month: int) -> str:
    return f"{MONTHS_NOMINATIVE[month - 1]} {year}"


def money(value) -> str:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = 0
    return f"{number:,}".replace(",", "\u202f") + "\u00a0₽"


def plural_ru(count: int, one: str, few: str, many: str) -> str:
    count = abs(int(count))
    if count % 10 == 1 and count % 100 != 11:
        return one
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return few
    return many


def guests_label(count: int) -> str:
    return f"{count} {plural_ru(count, 'гость', 'гостя', 'гостей')}"


def status_meta(status: str) -> tuple[str, str]:
    return BOOKING_STATUSES.get(status, (status, "muted"))


def role_label(role: str) -> str:
    return ROLE_LABELS.get(role, role)


# ---------------------------------------------------------------------------
# Валидация
# ---------------------------------------------------------------------------

def normalize_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = re.sub(r"[\s\-()]", "", raw.strip())
    if cleaned.startswith("8") and len(cleaned) == 11:
        cleaned = "+7" + cleaned[1:]
    if not PHONE_RE.match(cleaned):
        return None
    return cleaned


def pretty_phone(raw: str | None) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits[0] in "78":
        return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return raw or ""


def valid_email(value: str) -> bool:
    return bool(value and len(value) <= 254 and EMAIL_RE.match(value))


def password_errors(password: str) -> list[str]:
    errors: list[str] = []
    if len(password) < 8:
        errors.append("Пароль должен содержать минимум 8 символов.")
    if len(password) > 128:
        errors.append("Пароль слишком длинный (максимум 128 символов).")
    if not re.search(r"[A-Za-zА-Яа-я]", password):
        errors.append("Добавьте в пароль хотя бы одну букву.")
    if not re.search(r"\d", password):
        errors.append("Добавьте в пароль хотя бы одну цифру.")
    if password.lower() in COMMON_PASSWORDS:
        errors.append("Этот пароль слишком распространён — выберите другой.")
    return errors


def hash_password(password: str) -> str:
    return generate_password_hash(password, method="scrypt")


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return check_password_hash(password_hash, password)
    except (ValueError, TypeError):
        return False


def clean_text(value: str | None, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())[:limit]


# ---------------------------------------------------------------------------
# Токены и CSRF
# ---------------------------------------------------------------------------

def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = new_token(24)
        session["_csrf_token"] = token
    return token


def validate_csrf() -> None:
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
    stored = session.get("_csrf_token", "")
    if not sent or not stored or not hmac.compare_digest(str(sent), str(stored)):
        abort(400, description="CSRF-токен недействителен. Обновите страницу и попробуйте снова.")


def request_wants_json() -> bool:
    best = request.accept_mimetypes.best
    return (
        request.path.startswith("/api/")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or (best == "application/json" and request.accept_mimetypes[best] > request.accept_mimetypes["text/html"])
    )


def jsonify_error(message: str, status: int = 400):
    response = jsonify({"ok": False, "error": message})
    response.status_code = status
    return response


def safe_next_url(target: str | None) -> str | None:
    """Разрешает только локальные пути, защищает от open redirect."""
    if not target:
        return None
    target = target.strip()
    if target.startswith("//") or target.startswith("\\") or "\\" in target:
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return None
    if not parts.path.startswith("/") or parts.path.startswith("//"):
        return None
    return target


def wants_json_response() -> bool:
    return request_wants_json()


# ---------------------------------------------------------------------------
# Аутентификация и роли
# ---------------------------------------------------------------------------

def login_user(user) -> None:
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    session["session_version"] = user["session_version"]
    session["_csrf_token"] = new_token(24)


def logout_user() -> None:
    session.clear()


def load_logged_in_user() -> None:
    from database import get_db

    g.user = None
    user_id = session.get("user_id")
    if not user_id:
        return
    user = get_db().execute(
        "SELECT id, name, email, phone, role, session_version, is_active, created_at "
        "FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if (
        user is None
        or not user["is_active"]
        or session.get("session_version") != user["session_version"]
    ):
        session.clear()
        return
    g.user = user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            if request_wants_json():
                return jsonify_error("Требуется вход в аккаунт.", 401)
            flash("Войдите в аккаунт, чтобы продолжить.", "info")
            next_url = request.path
            if request.query_string:
                next_url += "?" + request.query_string.decode("utf-8", "ignore")
            return redirect(url_for("auth.login", next=next_url))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles: str):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


admin_required = role_required("admin", "owner")
owner_required = role_required("owner")


def verify_owner_or_admin(owner_id: int | None) -> None:
    """Разрешает доступ владельцу объекта, админу и владельцу ресторана."""
    if g.get("user") is None:
        abort(403)
    if g.user["role"] in ("admin", "owner"):
        return
    if owner_id is not None and owner_id == g.user["id"]:
        return
    abort(403)


# ---------------------------------------------------------------------------
# Настройки, IP, rate limit
# ---------------------------------------------------------------------------

def get_settings() -> dict[str, str]:
    if "settings" not in g:
        from database import get_db

        rows = get_db().execute("SELECT key, value FROM settings").fetchall()
        values = dict(DEFAULT_SETTINGS)
        values.update({row["key"]: row["value"] for row in rows})
        g.settings = values
    return g.settings


def client_ip() -> str:
    try:
        return request.remote_addr or "127.0.0.1"
    except RuntimeError:  # вне запроса (CLI, планировщик)
        return "cli"


_rate_lock = threading.Lock()
_rate_store: dict[str, list[float]] = {}


def rate_limit(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Простой потокобезопасный in-memory лимитер для одного процесса."""
    now = time.monotonic()
    bucket_key = key[:240]
    with _rate_lock:
        hits = [stamp for stamp in _rate_store.get(bucket_key, []) if stamp > now - window_seconds]
        if len(hits) >= limit:
            retry_after = max(1, int(window_seconds - (now - hits[0])))
            _rate_store[bucket_key] = hits
            return False, retry_after
        hits.append(now)
        _rate_store[bucket_key] = hits
    if len(_rate_store) > 5000:
        with _rate_lock:
            for k in list(_rate_store.keys())[:1000]:
                _rate_store.pop(k, None)
    return True, 0


def reset_rate_limits() -> None:
    with _rate_lock:
        _rate_store.clear()


# ---------------------------------------------------------------------------
# Загрузка изображений
# ---------------------------------------------------------------------------

ALLOWED_IMAGE_EXTENSIONS = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
IMAGE_SIGNATURES = {
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
}


def detect_image_type(data: bytes, filename: str) -> str | None:
    """Проверяет расширение и сигнатуру файла; возвращает MIME или None."""
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
    mime = ALLOWED_IMAGE_EXTENSIONS.get(ext)
    if not mime:
        return None
    if ext == "webp":
        if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return mime
        return None
    if not any(data.startswith(signature) for signature in IMAGE_SIGNATURES.get(ext, ())):
        return None
    # Отсекаем заведомо исполняемые форматы внутри картинки.
    head = data[:4096].lower()
    if b"<script" in head or b"<?php" in head:
        return None
    return mime


# ---------------------------------------------------------------------------
# Контекст шаблонов
# ---------------------------------------------------------------------------

def inject_globals() -> dict:
    return {
        "current_user": g.get("user"),
        "csrf_token": csrf_token,
        "settings": get_settings(),
        "booking_statuses": BOOKING_STATUSES,
        "role_labels": ROLE_LABELS,
        "now_year": utc_now().year,
        "demo_mode": current_app.config.get("DEMO_MODE", True),
    }


def query_url(**updates) -> str:
    """Собирает URL текущей страницы с обновлёнными query-параметрами."""
    args = request.args.to_dict(flat=True)
    args.update(updates)
    for key in list(args):
        if args[key] in (None, ""):
            args.pop(key)
    return url_for(request.endpoint or "public.home", **(request.view_args or {}), **args)
