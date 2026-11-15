"""Пользователи, аутентификация, сброс пароля и приватность."""
from __future__ import annotations

from datetime import timedelta

from core import (
    clean_text, hash_password, hash_token, new_token, normalize_phone, parse_stamp,
    password_errors, utc_now, utc_stamp, valid_email, verify_password,
)
from database import get_db
from services.audit import log_action

RESET_TTL_MINUTES = 60
ROLES = ("guest", "admin", "owner")


def get_user(user_id: int):
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def find_by_email(email: str):
    return get_db().execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email.strip(),)).fetchone()


def create_user(form) -> tuple[int | None, dict[str, str]]:
    db = get_db()
    errors: dict[str, str] = {}
    name = clean_text(form.get("name"), 80)
    email = (form.get("email") or "").strip().lower()[:254]
    phone_raw = (form.get("phone") or "").strip()
    phone = normalize_phone(phone_raw) if phone_raw else None
    password = form.get("password") or ""
    password2 = form.get("password2") or ""
    if len(name) < 2:
        errors["name"] = "Укажите имя (минимум 2 символа)."
    if not valid_email(email):
        errors["email"] = "Введите корректный email."
    elif find_by_email(email):
        errors["email"] = "Пользователь с таким email уже зарегистрирован."
    if phone_raw and not phone:
        errors["phone"] = "Телефон в формате +7 999 123-45-67."
    errors.update(_password_form_errors(password, password2))
    if not form.get("consent"):
        errors["consent"] = "Нужно согласие на обработку персональных данных."
    if errors:
        return None, errors
    now = utc_stamp()
    # Роль всегда guest: повышение через публичную форму невозможно.
    cursor = db.execute(
        "INSERT INTO users(name, email, phone, password_hash, role, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'guest', ?, ?)",
        (name, email, phone, hash_password(password), now, now),
    )
    db.commit()
    log_action("user.registered", "user", cursor.lastrowid, {"email": email})
    db.commit()
    return cursor.lastrowid, {}


def _password_form_errors(password: str, password2: str) -> dict[str, str]:
    errors: dict[str, str] = {}
    policy = password_errors(password)
    if policy:
        errors["password"] = policy[0]
    if password != password2:
        errors["confirm"] = "Пароли не совпадают."
    return errors


def authenticate(email: str, password: str):
    user = find_by_email((email or "").strip())
    if user is None or not user["is_active"]:
        return None
    if not verify_password(user["password_hash"], password or ""):
        return None
    return user


def update_profile(user_id: int, form) -> dict[str, str]:
    db = get_db()
    errors: dict[str, str] = {}
    name = clean_text(form.get("name"), 80)
    email = (form.get("email") or "").strip().lower()[:254]
    phone_raw = (form.get("phone") or "").strip()
    phone = normalize_phone(phone_raw) if phone_raw else None
    if len(name) < 2:
        errors["name"] = "Укажите имя (минимум 2 символа)."
    if not valid_email(email):
        errors["email"] = "Введите корректный email."
    else:
        other = db.execute(
            "SELECT id FROM users WHERE email = ? COLLATE NOCASE AND id != ?", (email, user_id)
        ).fetchone()
        if other:
            errors["email"] = "Этот email уже используется."
    if phone_raw and not phone:
        errors["phone"] = "Телефон в формате +7 999 123-45-67."
    if errors:
        return errors
    db.execute(
        "UPDATE users SET name = ?, email = ?, phone = ?, updated_at = ? WHERE id = ?",
        (name, email, phone, utc_stamp(), user_id),
    )
    db.commit()
    log_action("user.profile_updated", "user", user_id)
    db.commit()
    return {}


def change_password(user_id: int, current: str, new: str, new2: str) -> dict[str, str]:
    db = get_db()
    user = get_user(user_id)
    if not user:
        return {"_": "Пользователь не найден."}
    errors: dict[str, str] = {}
    if not verify_password(user["password_hash"], current or ""):
        errors["current"] = "Текущий пароль неверен."
    policy = password_errors(new or "")
    if policy:
        errors["new"] = policy[0]
    if new != new2:
        errors["new2"] = "Пароли не совпадают."
    if not errors and verify_password(user["password_hash"], new):
        errors["new"] = "Новый пароль должен отличаться от текущего."
    if errors:
        return errors
    db.execute(
        "UPDATE users SET password_hash = ?, session_version = session_version + 1, updated_at = ? "
        "WHERE id = ?",
        (hash_password(new), utc_stamp(), user_id),
    )
    db.commit()
    log_action("user.password_changed", "user", user_id)
    db.commit()
    return {}


def request_password_reset(email: str) -> str | None:
    db = get_db()
    user = find_by_email(email or "")
    if not user or not user["is_active"]:
        return None
    token = new_token(32)
    now = utc_stamp()
    expires = (utc_now() + timedelta(minutes=RESET_TTL_MINUTES)).strftime("%Y-%m-%dT%H:%M:%SZ")
    db.execute("UPDATE password_resets SET used_at = ? WHERE user_id = ? AND used_at IS NULL", (now, user["id"]))
    db.execute(
        "INSERT INTO password_resets(user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (user["id"], hash_token(token), expires, now),
    )
    db.commit()
    log_action("user.reset_requested", "user", user["id"])
    db.commit()
    return token


def find_reset(token: str):
    if not token or len(token) > 128:
        return None
    row = get_db().execute(
        "SELECT pr.*, u.email, u.name FROM password_resets pr "
        "JOIN users u ON u.id = pr.user_id WHERE pr.token_hash = ?",
        (hash_token(token),),
    ).fetchone()
    if not row or row["used_at"]:
        return None
    expires = parse_stamp(row["expires_at"])
    if not expires or expires <= utc_now():
        return None
    return row


def reset_password(token: str, password: str, password2: str) -> tuple[int | None, dict[str, str]]:
    row = find_reset(token)
    if not row:
        return None, {"_": "Ссылка недействительна или истекла. Запросите новую."}
    policy = password_errors(password or "")
    if policy:
        return None, {"password": policy[0]}
    if password != password2:
        return None, {"password2": "Пароли не совпадают."}
    db = get_db()
    now = utc_stamp()
    db.execute(
        "UPDATE users SET password_hash = ?, session_version = session_version + 1, updated_at = ? "
        "WHERE id = ?",
        (hash_password(password), now, row["user_id"]),
    )
    db.execute("UPDATE password_resets SET used_at = ? WHERE id = ?", (now, row["id"]))
    db.commit()
    log_action("user.password_reset", "user", row["user_id"], actor_id=row["user_id"])
    db.commit()
    return row["user_id"], {}


def delete_account(user_id: int, password: str) -> dict[str, str]:
    db = get_db()
    user = get_user(user_id)
    if not user:
        return {"_": "Пользователь не найден."}
    if user["role"] != "guest":
        return {"_": "Аккаунты администраторов и владельца удаляются только через владельца."}
    if not verify_password(user["password_hash"], password or ""):
        return {"password": "Пароль неверен."}
    now = utc_stamp()
    db.execute(
        "UPDATE bookings SET user_id = NULL, guest_name = 'Удалённый гость', guest_phone = '+70000000000', "
        "guest_email = NULL, comment = NULL, updated_at = ? WHERE user_id = ?",
        (now, user_id),
    )
    db.execute(
        "UPDATE reviews SET user_id = NULL, author_name = 'Гость' WHERE user_id = ?", (user_id,)
    )
    log_action("user.deleted", "user", user_id, {"email": user["email"]}, actor_id=None)
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    return {}


def export_user_data(user_id: int) -> dict:
    db = get_db()
    user = get_user(user_id)
    if not user:
        return {}
    bookings = db.execute(
        "SELECT code, date, time, guests_count, status, occasion, comment, created_at "
        "FROM bookings WHERE user_id = ? ORDER BY date DESC", (user_id,)
    ).fetchall()
    favorites = db.execute(
        "SELECT d.name, d.price FROM favorites f JOIN dishes d ON d.id = f.dish_id WHERE f.user_id = ?",
        (user_id,),
    ).fetchall()
    reviews = db.execute(
        "SELECT rating, text, status, created_at FROM reviews WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    notifications = db.execute(
        "SELECT title, body, created_at FROM notifications WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    return {
        "profile": {"name": user["name"], "email": user["email"], "phone": user["phone"],
                    "created_at": user["created_at"]},
        "bookings": [dict(row) for row in bookings],
        "favorites": [dict(row) for row in favorites],
        "reviews": [dict(row) for row in reviews],
        "notifications": [dict(row) for row in notifications],
        "exported_at": utc_stamp(),
    }


def list_users(q: str | None = None, role: str | None = None) -> list:
    db = get_db()
    where, params = [], []
    if q:
        term = f"%{q.strip()[:80]}%"
        where.append("(name LIKE ? OR email LIKE ? OR phone LIKE ?)")
        params.extend([term, term, term])
    if role in ROLES:
        where.append("role = ?")
        params.append(role)
    sql = "SELECT * FROM users"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY role, created_at DESC"
    return db.execute(sql, params).fetchall()


def set_user_role(actor, target_id: int, role: str) -> dict[str, str]:
    db = get_db()
    target = get_user(target_id)
    if not target:
        return {"_": "Пользователь не найден."}
    if role not in ("guest", "admin"):
        return {"role": "Можно назначить только роль «Гость» или «Администратор»."}
    if target["id"] == actor["id"]:
        return {"_": "Нельзя изменить собственную роль."}
    if target["role"] == "owner":
        return {"_": "Роль владельца изменить нельзя."}
    db.execute("UPDATE users SET role = ?, updated_at = ? WHERE id = ?", (role, utc_stamp(), target_id))
    db.execute("UPDATE users SET session_version = session_version + 1 WHERE id = ?", (target_id,))
    db.commit()
    log_action("user.role_changed", "user", target_id, {"role": role, "email": target["email"]})
    db.commit()
    return {}


def user_stats() -> dict:
    db = get_db()
    rows = db.execute("SELECT role, COUNT(*) AS n FROM users GROUP BY role").fetchall()
    return {row["role"]: row["n"] for row in rows}
