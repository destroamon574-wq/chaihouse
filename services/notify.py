"""Внешние уведомления: Telegram для ресторана, e-mail гостю, напоминания о брони.

Без внешних зависимостей: Telegram — через HTTPS Bot API, почта — через smtplib.
Всё настроено необязательно: нет токена/SMTP — функция мягко пропускается,
ошибки сети не ломают бронирование (пишем запись в журнал действий).
"""

from __future__ import annotations

import json
import os
import smtplib
import urllib.error
import urllib.request
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formataddr

from core import get_settings, ru_date, utc_stamp
from database import get_db
from services.audit import log_action

TELEGRAM_TIMEOUT = 5
SMTP_TIMEOUT = 10

STATUS_LABELS = {
    "confirmed": "подтверждена ✅",
    "declined": "отклонена ❌",
    "cancelled": "отменена",
    "completed": "завершена",
}


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------


def telegram_configured(settings: dict | None = None) -> bool:
    values = settings or get_settings()
    return bool(
        (values.get("telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN"))
        and (values.get("telegram_chat_id") or os.environ.get("TELEGRAM_CHAT_ID"))
    )


def send_telegram(text: str, settings: dict | None = None) -> bool:
    """Шлёт сообщение в чат ресторана. True — отправлено, False — не настроено/ошибка."""
    values = settings or get_settings()
    token = values.get("telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = values.get("telegram_chat_id") or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text[:3800]}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TELEGRAM_TIMEOUT) as response:
            ok = response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        log_action("notify.telegram_failed", "system", "telegram", {"error": str(error)[:200]})
        return False
    if not ok:
        log_action("notify.telegram_failed", "system", "telegram", {"status": "non-200"})
    return ok


# ---------------------------------------------------------------------------
# E-mail
# ---------------------------------------------------------------------------


def smtp_configured() -> bool:
    return bool(os.environ.get("SMTP_HOST"))


def _smtp_params() -> dict:
    return {
        "host": os.environ.get("SMTP_HOST", ""),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "from_addr": os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "")),
        "from_name": os.environ.get("SMTP_FROM_NAME", "ЧайHouse"),
    }


def send_email(to_addr: str, subject: str, body: str) -> bool:
    """Шлёт текстовое письмо через SMTP. False — не настроено или ошибка."""
    if not to_addr or not smtp_configured():
        return False
    params = _smtp_params()
    message = EmailMessage()
    message["From"] = formataddr((params["from_name"], params["from_addr"]))
    message["To"] = to_addr
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(params["host"], params["port"], timeout=SMTP_TIMEOUT) as smtp:
            smtp.starttls()
            if params["user"]:
                smtp.login(params["user"], params["password"])
            smtp.send_message(message)
    except (smtplib.SMTPException, TimeoutError, OSError) as error:
        log_action("notify.email_failed", "system", "email", {"error": str(error)[:200], "to": to_addr[:80]})
        return False
    return True


# ---------------------------------------------------------------------------
# События бронирования
# ---------------------------------------------------------------------------


def notify_admins_new_booking(booking: dict) -> bool:
    """Мгновенное сообщение в Telegram ресторана о новой брони."""
    settings = get_settings()
    if not telegram_configured(settings):
        return False
    text = (
        "🆕 Новая бронь\n"
        f"{booking['guest_name']} — {ru_date(booking['date'], 'day')} в {booking['time']}\n"
        f"{booking['hall_name']}, {booking['table_name']} · {booking['guests']} чел.\n"
        f"Код: {booking['code']}"
    )
    sent = send_telegram(text, settings)
    if not sent:
        log_action("notify.skipped", "system", "telegram", {"reason": "not configured or failed"})
    return sent


def notify_guest_status(booking, new_status: str, reason: str = "") -> bool:
    """Письмо гостю при смене статуса брони (когда у него указан e-mail)."""
    if not booking["guest_email"] or new_status not in STATUS_LABELS:
        return False
    label = STATUS_LABELS[new_status]
    subject = f"ЧайHouse: бронь {booking['code']} {label}"
    lines = [
        f"Здравствуйте, {booking['guest_name']}!",
        "",
        f"Ваша бронь {booking['code']} {label}:",
        f"Дата: {ru_date(booking['date'], 'day')}",
        f"Время: {booking['time']} · {booking['hall_name']}, {booking['table_name']}",
        f"Гостей: {booking['guests_count']}",
    ]
    if reason:
        lines.append(f"Комментарий: {reason}")
    lines += ["", "ЧайHouse — ждём вас!"]
    sent = send_email(booking["guest_email"], subject, "\n".join(lines))
    if not sent and not smtp_configured():
        log_action("notify.skipped", "system", "email", {"reason": "SMTP not configured"})
    return sent


# ---------------------------------------------------------------------------
# Напоминания
# ---------------------------------------------------------------------------


def tomorrow_bookings() -> list:
    """Подтверждённые брони на завтра, по которым ещё не отправляли напоминание."""
    from services.bookings import today_local

    tomorrow = today_local() + timedelta(days=1)
    db = get_db()
    return db.execute(
        "SELECT b.*, h.name AS hall_name, t.name AS table_name FROM bookings b "
        "JOIN halls h ON h.id = b.hall_id JOIN dining_tables t ON t.id = b.table_id "
        "WHERE b.date = ? AND b.status = 'confirmed' AND b.reminded_at IS NULL "
        "ORDER BY b.time",
        (tomorrow.isoformat(),),
    ).fetchall()


def _reminder_text(booking) -> str:
    return (
        f"Напоминаем о вашей брони в ЧайHouse:\n"
        f"Завтра, {ru_date(booking['date'], 'day')} в {booking['time']}\n"
        f"{booking['hall_name']}, {booking['table_name']} · {booking['guests_count']} чел.\n"
        f"Код брони: {booking['code']}\n\n"
        f"Если планы изменились — отмените бронь на сайте или позвоните нам."
    )


def send_upcoming_reminders() -> tuple[int, int]:
    """Напоминания о завтрашних бронях: e-mail гостю (или письмо-заготовка админу).

    Возвращает (отправлено, пропущено_без_контакта). Брони помечаются reminded_at,
    чтобы не отправлять повторно.
    """
    db = get_db()
    sent = skipped = 0
    for booking in tomorrow_bookings():
        delivered = send_email(
            booking["guest_email"] or "",
            f"ЧайHouse: завтра ваша бронь {booking['code']}",
            _reminder_text(booking),
        )
        if delivered:
            sent += 1
        else:
            skipped += 1
            if booking["user_id"]:
                from services.notifications import create_notification

                create_notification(
                    booking["user_id"],
                    "Завтра ваша бронь",
                    f"Ждём вас завтра в {booking['time']}, {booking['hall_name']}, "
                    f"{booking['table_name']}. Код брони: {booking['code']}.",
                    f"/account/bookings/{booking['code']}",
                )
        db.execute("UPDATE bookings SET reminded_at = ? WHERE id = ?", (utc_stamp(), booking["id"]))
    if sent or skipped:
        db.commit()
        log_action("notify.reminders_sent", "system", "bookings", {"sent": sent, "skipped": skipped})
        db.commit()
    return sent, skipped
