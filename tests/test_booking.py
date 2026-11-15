"""Бронирование: доступ, слоты, конфликты, поиск и отмена."""
from __future__ import annotations

from datetime import date, timedelta

from conftest import (
    csrf_for, extract_csrf, first_table_id, future_date, hall_id, login, past_date,
)


def _booking_payload(app, overrides=None) -> dict:
    payload = {
        "hall_id": str(hall_id(app)),
        "table_id": str(first_table_id(app)),
        "date": future_date(7),
        "time": "12:00",
        "guests": "2",
        "name": "Тестовый Гость",
        "phone": "+79991234567",
        "email": "booking@example.com",
        "occasion": "Ужин",
        "comment": "Стол у окна, если можно.",
        "consent": "1",
    }
    if overrides:
        payload.update(overrides)
    return payload


def _create_booking(client, app, overrides=None):
    token = csrf_for(client, "/booking")
    return client.post("/booking", data={"csrf_token": token, **_booking_payload(app, overrides)},
                       follow_redirects=False)


def _booking_code(location: str) -> str:
    return location.rsplit("/", 1)[-1]


def test_booking_requires_login(client):
    response = client.get("/booking", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/auth/login")
    assert "next=" in response.headers["Location"]

    token = csrf_for(client, "/auth/login")
    posted = client.post("/booking", data={"csrf_token": token, **_booking_payload_or_none()},
                         follow_redirects=False)
    assert posted.status_code == 302
    assert posted.headers["Location"].startswith("/auth/login")


def _booking_payload_or_none() -> dict:
    return {"date": future_date(7), "time": "12:00", "guests": "2",
            "name": "Гость", "phone": "+79991234567", "consent": "1"}


def test_logged_in_guest_sees_booking_page(client):
    login(client)
    response = client.get("/booking")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Забронировать стол" in body
    assert "Основной зал" in body
    assert 'name="csrf_token"' in body


def test_guest_can_create_booking(client, app):
    login(client)
    response = _create_booking(client, app)
    assert response.status_code == 302
    assert "/booking/success/" in response.headers["Location"]

    code = _booking_code(response.headers["Location"])
    page = client.get(f"/booking/success/{code}")
    assert page.status_code == 200
    assert code in page.get_data(as_text=True)

    with app.app_context():
        from database import get_db

        row = get_db().execute("SELECT * FROM bookings WHERE code = ?", (code,)).fetchone()
        assert row is not None
        assert row["status"] == "pending"
        assert row["guest_name"] == "Тестовый Гость"
        assert row["user_id"] is not None


def test_booking_conflict_is_rejected(client, app):
    login(client)
    first = _create_booking(client, app)
    assert first.status_code == 302
    second = _create_booking(client, app)
    assert second.status_code == 422
    body = second.get_data(as_text=True)
    assert "занят" in body.lower() or "только что забронировали" in body.lower()


def test_booking_past_date_is_rejected(client, app):
    login(client)
    response = _create_booking(client, app, {"date": past_date()})
    assert response.status_code == 422
    assert "прошедшую" in response.get_data(as_text=True).lower()


def test_booking_far_future_date_is_rejected(client, app):
    login(client)
    too_far = (date.today() + timedelta(days=200)).isoformat()
    response = _create_booking(client, app, {"date": too_far})
    assert response.status_code == 422
    assert "90 дней" in response.get_data(as_text=True)


def test_booking_guests_limit_is_validated(client, app):
    login(client)
    response = _create_booking(client, app, {"guests": "25"})
    assert response.status_code == 422
    assert "от 1 до" in response.get_data(as_text=True)


def test_booking_requires_consent_and_valid_phone(client, app):
    login(client)
    no_consent = _create_booking(client, app, {"consent": ""})
    assert no_consent.status_code == 422
    assert "согласи" in no_consent.get_data(as_text=True).lower()

    bad_phone = _create_booking(client, app, {"phone": "123"})
    assert bad_phone.status_code == 422
    assert "телефон" in bad_phone.get_data(as_text=True).lower()


def test_booking_lookup_by_code_and_phone(client):
    token = csrf_for(client, "/booking/lookup")
    found = client.post(
        "/booking/lookup",
        data={"csrf_token": token, "code": "CH-DEMO01", "phone": "+7 999 000-11-22"},
        follow_redirects=False,
    )
    assert found.status_code == 302
    assert "/booking/success/CH-DEMO01" in found.headers["Location"]
    assert client.get("/booking/success/CH-DEMO01").status_code == 200

    token = csrf_for(client, "/booking/lookup")
    wrong = client.post(
        "/booking/lookup",
        data={"csrf_token": token, "code": "CH-DEMO01", "phone": "+79990000000"},
    )
    assert wrong.status_code == 200
    assert "не найдена" in wrong.get_data(as_text=True)


def test_success_page_blocks_other_booking(client):
    login(client)
    response = client.get("/booking/success/CH-DEMO03")
    assert response.status_code == 404


def test_guest_can_cancel_own_booking(client, app):
    login(client)
    created = _create_booking(client, app, {"date": future_date(9), "time": "13:00"})
    code = _booking_code(created.headers["Location"])

    token = extract_csrf(client.get(f"/booking/success/{code}"))
    cancelled = client.post(
        f"/booking/{code}/cancel",
        data={"csrf_token": token, "reason": "Изменились планы"},
        follow_redirects=False,
    )
    assert cancelled.status_code == 302
    with app.app_context():
        from database import get_db

        row = get_db().execute("SELECT status, cancel_reason FROM bookings WHERE code = ?", (code,)).fetchone()
        assert row["status"] == "cancelled"
        assert row["cancel_reason"] == "Изменились планы"


def test_booking_ics_calendar(client, app):
    login(client)
    created = _create_booking(client, app, {"date": future_date(11), "time": "14:00"})
    code = _booking_code(created.headers["Location"])

    response = client.get(f"/booking/{code}/calendar.ics")
    assert response.status_code == 200
    assert "text/calendar" in response.headers["Content-Type"]
    assert "chaihouse-" in response.headers["Content-Disposition"]
    body = response.get_data(as_text=True)
    assert "BEGIN:VCALENDAR" in body
    assert "BEGIN:VEVENT" in body
    assert code in body


def test_ics_denied_for_foreign_booking(client, app):
    login(client)
    response = client.get("/booking/CH-DEMO02/calendar.ics")
    assert response.status_code == 404
