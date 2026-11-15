"""Тесты новых возможностей v1.1: календарь, аналитика, бэкап, уведомления, отзывы."""

from __future__ import annotations

from datetime import timedelta

import pytest

from tests.conftest import extract_csrf, login, moscow_today


@pytest.fixture
def app(tmp_path):
    from app import create_app

    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "DATABASE_PATH": str(tmp_path / "test.db"),
            "UPLOAD_DIR": str(tmp_path / "uploads"),
            "SITE_URL": "http://localhost",
            "AUTO_SEED": True,
            "DEMO_MODE": True,
        }
    )
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


def _make_booking(
    app,
    *,
    code="CH-TEST99",
    status="confirmed",
    hall_slug="osnovnoy-zal",
    days_ahead=1,
    guest_email="guest@chaihouse.ru",
    user_id=3,
):
    from database import get_db

    with app.app_context():
        db = get_db()
        hall = db.execute("SELECT id FROM halls WHERE slug = ?", (hall_slug,)).fetchone()
        table = db.execute(
            "SELECT id FROM dining_tables WHERE hall_id = ? ORDER BY seats LIMIT 1", (hall["id"],)
        ).fetchone()
        date_value = (moscow_today() + timedelta(days=days_ahead)).isoformat()
        db.execute(
            "INSERT INTO bookings(code, user_id, hall_id, table_id, guest_name, guest_phone, "
            "guest_email, date, time, start_min, end_min, guests_count, occasion, status, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                code,
                user_id,
                hall["id"],
                table["id"],
                "Тест Гость",
                "+79990000000",
                guest_email,
                date_value,
                "19:00",
                19 * 60,
                21 * 60,
                4,
                "Ужин",
                status,
                "2026-01-01T10:00:00Z",
                "2026-01-01T10:00:00Z",
            ),
        )
        db.commit()
        row = db.execute("SELECT * FROM bookings WHERE code = ?", (code,)).fetchone()
        return dict(row)


def test_migration_adds_reminded_at(app):
    from database import get_db

    with app.app_context():
        columns = {row["name"] for row in get_db().execute("PRAGMA table_info(bookings)").fetchall()}
        assert "reminded_at" in columns


def test_admin_calendar_requires_admin(client):
    response = client.get("/admin/calendar")
    assert response.status_code == 302  # редирект на вход


def test_admin_calendar_renders_week(client):
    assert login(client, "admin@chaihouse.ru", "Admin#2026").status_code == 302
    response = client.get("/admin/calendar")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Календарь загрузки" in body
    assert "Основной зал" in body


def test_admin_calendar_shows_booking(client, app):
    _make_booking(app, code="CH-GRID01", days_ahead=0)
    assert login(client, "admin@chaihouse.ru", "Admin#2026").status_code == 302
    response = client.get("/admin/calendar")
    assert "CH-GRID01" in response.get_data(as_text=True)


def test_analytics_functions(app):
    from services.analytics import guest_insights, hall_occupancy_month, weekday_stats

    with app.app_context():
        insights = guest_insights()
        assert set(insights) == {"period_days", "repeat_guests", "visitors", "booked", "conversion"}
        weekdays = weekday_stats()
        assert len(weekdays) == 7
        assert all("avg_guests" in day for day in weekdays)
        occupancy = hall_occupancy_month()
        assert occupancy and all(0 <= hall["occupancy"] <= 100 for hall in occupancy)


def test_owner_backup_route(client, app):
    assert login(client, "owner@chaihouse.ru", "Owner#2026").status_code == 302
    token = extract_csrf(client.get("/owner/"))
    response = client.post("/owner/backup", data={"csrf_token": token})
    assert response.status_code == 302
    from pathlib import Path

    directory = Path(app.config["DATABASE_PATH"]).parent / "backups"
    files = list(directory.glob("chaihouse-*.db"))
    assert len(files) == 1
    assert files[0].stat().st_size > 0


def test_backup_script_function(app):
    from pathlib import Path

    from services.backup import create_backup

    with app.app_context():
        target, kept = create_backup()
        assert Path(target).exists()
        assert kept == 1


def test_notify_not_configured(app):
    from services.notify import notify_admins_new_booking, telegram_configured

    with app.app_context():
        assert telegram_configured() is False
        assert (
            notify_admins_new_booking(
                {
                    "guest_name": "X",
                    "date": "2026-01-01",
                    "time": "19:00",
                    "hall_name": "Зал",
                    "table_name": "Стол 1",
                    "guests": 2,
                    "code": "CH-1",
                }
            )
            is False
        )


def test_reminders_mark_and_skip_repeat(app):
    from database import get_db
    from services.notify import send_upcoming_reminders

    _make_booking(app, code="CH-REM01", status="confirmed", guest_email=None, user_id=None)
    with app.app_context():
        sent, skipped = send_upcoming_reminders()
        assert sent == 0
        assert skipped >= 1  # наша бронь без e-mail и без аккаунта — пропущена
        reminded = (
            get_db()
            .execute("SELECT reminded_at FROM bookings WHERE code = 'CH-REM01'")
            .fetchone()["reminded_at"]
        )
        assert reminded
        # Повторный запуск не находит броней
        assert send_upcoming_reminders() == (0, 0)


def test_hall_page_shows_hall_reviews(client, app):
    from database import get_db

    booking = _make_booking(app, code="CH-REV01", days_ahead=-5, status="completed")
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO reviews(user_id, booking_id, author_name, rating, text, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'published', '2026-01-05T12:00:00Z')",
            (
                3,
                booking["id"],
                "Тест Гость",
                5,
                "Отличный зал, тёплый свет и вкусный плов!",
            ),
        )
        db.commit()
    response = client.get("/halls/osnovnoy-zal")
    assert response.status_code == 200
    assert "Гости об этом зале" in response.get_data(as_text=True)
    assert "Отличный зал" in response.get_data(as_text=True)


def test_home_shows_top_reviews(client, app):
    response = client.get("/")
    body = response.get_data(as_text=True)
    assert "Плов здесь действительно особенный" in body  # seed-отзыв с оценкой 5


def test_owner_settings_saves_telegram(client, app):
    assert login(client, "owner@chaihouse.ru", "Owner#2026").status_code == 302
    token = extract_csrf(client.get("/owner/settings"))
    response = client.post(
        "/owner/settings",
        data={
            "csrf_token": token,
            "restaurant_name": "ЧайHouse",
            "tagline": "Восточная кухня",
            "phone": "+7 (495) 120-48-18",
            "email": "hello@chaihouse.example",
            "address": "Москва, Ходынский бульвар, 4",
            "address_short": "Ходынский бульвар, 4",
            "hours": "Ежедневно 12:00–00:00",
            "lat": "55.790622",
            "lng": "37.532186",
            "avg_check": "2400",
            "max_guests": "20",
            "booking_note": "Подтверждаем бронь в течение 15 минут.",
            "legal_name": "ООО «ЧайHouse»",
            "telegram_bot_token": "12345:ABC-test",
            "telegram_chat_id": "-100123",
        },
    )
    assert response.status_code == 302
    from database import get_db

    with app.app_context():
        row = get_db().execute("SELECT value FROM settings WHERE key = 'telegram_bot_token'").fetchone()
        assert row["value"] == "12345:ABC-test"


def test_telegram_configured_after_settings(app):
    from database import get_db
    from services.notify import telegram_configured

    with app.app_context():
        db = get_db()
        db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('telegram_bot_token', 't1')")
        db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('telegram_chat_id', 'c1')")
        db.commit()
        assert telegram_configured() is True
