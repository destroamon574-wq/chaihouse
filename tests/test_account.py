"""Личный кабинет гостя: избранное, уведомления, экспорт и приватность."""
from __future__ import annotations

from conftest import csrf_for, extract_csrf, login


def _user_id(app, email: str) -> int:
    with app.app_context():
        from database import get_db

        row = get_db().execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        assert row
        return int(row["id"])


def test_account_pages_open_for_guest(client):
    login(client)
    for path in ("/account/", "/account/bookings", "/account/favorites",
                 "/account/notifications", "/account/settings", "/account/delete"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "ЧайHouse" in response.get_data(as_text=True)


def test_guest_sees_own_booking_but_not_foreign(client):
    login(client)
    own = client.get("/account/bookings/CH-DEMO01")
    assert own.status_code == 200
    assert "CH-DEMO01" in own.get_data(as_text=True)

    foreign = client.get("/account/bookings/CH-DEMO03")
    assert foreign.status_code == 403


def test_favorite_toggle_ajax(client, app):
    login(client)
    token = extract_csrf(client.get("/account/favorites"))

    added = client.post(
        "/account/favorites/2",
        data={"csrf_token": token},
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    )
    assert added.status_code == 200
    payload = added.get_json()
    assert payload["ok"] is True
    assert payload["active"] is True

    with app.app_context():
        from database import get_db

        user_id = get_db().execute("SELECT id FROM users WHERE email = 'guest@chaihouse.ru'").fetchone()["id"]
        row = get_db().execute("SELECT 1 FROM favorites WHERE user_id = ? AND dish_id = 2", (user_id,)).fetchone()
        assert row is not None

    removed = client.post(
        "/account/favorites/2",
        data={"csrf_token": token},
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    )
    assert removed.get_json()["active"] is False


def test_favorite_missing_dish_returns_json_error(client):
    login(client)
    token = extract_csrf(client.get("/account/favorites"))
    response = client.post(
        "/account/favorites/99999",
        data={"csrf_token": token},
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    )
    assert response.status_code == 404
    assert response.get_json()["ok"] is False


def test_notifications_mark_all_read(client, app):
    login(client)
    page = client.get("/account/notifications")
    assert "Бронь подтверждена" in page.get_data(as_text=True)

    token = extract_csrf(page)
    response = client.post("/account/notifications/read-all", data={"csrf_token": token},
                           follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        from database import get_db

        user_id = get_db().execute("SELECT id FROM users WHERE email = 'guest@chaihouse.ru'").fetchone()["id"]
        unread = get_db().execute(
            "SELECT COUNT(*) AS n FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,)
        ).fetchone()["n"]
        assert unread == 0


def test_profile_update(client, app):
    login(client)
    token = extract_csrf(client.get("/account/settings"))
    response = client.post(
        "/account/settings",
        data={
            "csrf_token": token,
            "name": "Анна Обновлённая",
            "email": "guest@chaihouse.ru",
            "phone": "+7 999 111-22-33",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        from database import get_db

        row = get_db().execute("SELECT name, phone FROM users WHERE email = 'guest@chaihouse.ru'").fetchone()
        assert row["name"] == "Анна Обновлённая"
        assert row["phone"] == "+79991112233"


def test_profile_rejects_duplicate_email(client):
    login(client)
    token = extract_csrf(client.get("/account/settings"))
    response = client.post(
        "/account/settings",
        data={
            "csrf_token": token,
            "name": "Анна Соколова",
            "email": "owner@chaihouse.ru",
            "phone": "",
        },
    )
    assert response.status_code == 200
    assert "уже используется" in response.get_data(as_text=True)


def test_export_personal_data(client):
    login(client)
    response = client.get("/account/export")
    assert response.status_code == 200
    assert "application/json" in response.headers["Content-Type"]
    assert "attachment" in response.headers["Content-Disposition"]
    payload = response.get_json()
    assert payload["profile"]["email"] == "guest@chaihouse.ru"
    assert "bookings" in payload and "favorites" in payload


def test_delete_account_requires_password_and_anonymizes(client, app):
    login(client)
    token = extract_csrf(client.get("/account/delete"))

    wrong = client.post("/account/delete", data={"csrf_token": token, "password": "wrong-pass"})
    assert wrong.status_code == 200
    assert "Пароль неверен" in wrong.get_data(as_text=True)

    user_id = _user_id(app, "guest@chaihouse.ru")
    deleted = client.post(
        "/account/delete",
        data={"csrf_token": token, "password": "Guest#2026"},
        follow_redirects=False,
    )
    assert deleted.status_code == 302
    assert deleted.headers["Location"] == "/"

    with app.app_context():
        from database import get_db

        db = get_db()
        assert db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None
        booking = db.execute("SELECT guest_name, guest_phone, user_id FROM bookings WHERE code = 'CH-DEMO01'").fetchone()
        assert booking["guest_name"] == "Удалённый гость"
        assert booking["user_id"] is None


def test_admin_account_cannot_be_deleted_through_cabinet(client):
    login(client, "admin@chaihouse.ru", "Admin#2026")
    token = csrf_for(client, "/account/delete")
    response = client.post("/account/delete", data={"csrf_token": token, "password": "Admin#2026"})
    assert response.status_code == 200
    assert "только через владельца" in response.get_data(as_text=True)
