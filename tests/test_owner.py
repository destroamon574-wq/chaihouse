"""Кабинет владельца: аналитика, роли, настройки и экспорт."""

from __future__ import annotations

from conftest import csrf_for, login

SETTINGS_FORM = {
    "restaurant_name": "ЧайHouse Тест",
    "tagline": "Восточная кухня и чай",
    "address": "Москва, Ходынский бульвар, 4",
    "address_short": "Ходынский бульвар, 4",
    "phone": "+7 (495) 120-48-18",
    "email": "hello@chaihouse.example",
    "hours": "Ежедневно 12:00–00:00",
    "booking_note": "Подтверждаем бронь в течение 15 минут.",
    "legal_name": "ООО «ЧайHouse»",
    "avg_check": "2600",
    "max_guests": "18",
    "lat": "55.790622",
    "lng": "37.532186",
}


def _row(app, sql: str, params=()):
    with app.app_context():
        from database import get_db

        return get_db().execute(sql, params).fetchone()


def test_admin_cannot_open_owner_panel(client):
    login(client, "admin@chaihouse.ru", "Admin#2026")
    for path in ("/owner/", "/owner/users", "/owner/settings", "/owner/export.csv"):
        assert client.get(path).status_code == 403, path


def test_guest_cannot_open_owner_panel(client):
    login(client)
    assert client.get("/owner/").status_code == 403


def test_owner_dashboard_has_analytics(client):
    login(client, "owner@chaihouse.ru", "Owner#2026")
    response = client.get("/owner/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Показатели ЧайHouse" in body
    assert "Оценка выручки" in body
    assert "Брони за 14 дней" in body
    assert "chart-svg" in body


def test_owner_can_change_user_role(client, app):
    login(client, "owner@chaihouse.ru", "Owner#2026")
    guest = _row(app, "SELECT id, role FROM users WHERE email = 'guest@chaihouse.ru'")
    token = csrf_for(client, "/owner/users")

    promoted = client.post(
        f"/owner/users/{guest['id']}/role",
        data={"csrf_token": token, "role": "admin"},
        follow_redirects=False,
    )
    assert promoted.status_code == 302
    assert _row(app, "SELECT role FROM users WHERE id = ?", (guest["id"],))["role"] == "admin"

    client.post(f"/owner/users/{guest['id']}/role", data={"csrf_token": token, "role": "guest"})
    assert _row(app, "SELECT role FROM users WHERE id = ?", (guest["id"],))["role"] == "guest"


def test_owner_cannot_change_own_role_or_owner_role(client, app):
    login(client, "owner@chaihouse.ru", "Owner#2026")
    owner = _row(app, "SELECT id FROM users WHERE email = 'owner@chaihouse.ru'")
    token = csrf_for(client, "/owner/users")

    response = client.post(
        f"/owner/users/{owner['id']}/role",
        data={"csrf_token": token, "role": "admin"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "собственную роль" in response.get_data(as_text=True)
    assert _row(app, "SELECT role FROM users WHERE id = ?", (owner["id"],))["role"] == "owner"


def test_owner_settings_update_changes_public_site(client, app):
    login(client, "owner@chaihouse.ru", "Owner#2026")
    token = csrf_for(client, "/owner/settings")

    response = client.post(
        "/owner/settings", data={"csrf_token": token, **SETTINGS_FORM}, follow_redirects=False
    )
    assert response.status_code == 302
    assert _row(app, "SELECT value FROM settings WHERE key = 'restaurant_name'")["value"] == "ЧайHouse Тест"
    assert _row(app, "SELECT value FROM settings WHERE key = 'max_guests'")["value"] == "18"
    assert "ЧайHouse Тест" in client.get("/").get_data(as_text=True)


def test_owner_settings_validation(client):
    login(client, "owner@chaihouse.ru", "Owner#2026")
    token = csrf_for(client, "/owner/settings")
    response = client.post(
        "/owner/settings",
        data={"csrf_token": token, **SETTINGS_FORM, "lat": "999", "email": "not-an-email", "max_guests": "0"},
    )
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Проверьте координаты" in body
    assert "Проверьте email" in body
    assert "Максимум гостей" in body


def test_owner_csv_export(client):
    login(client, "owner@chaihouse.ru", "Owner#2026")
    response = client.get("/owner/export.csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["Content-Type"]
    assert "attachment" in response.headers["Content-Disposition"]
    body = response.get_data(as_text=True)
    assert "CH-DEMO01" in body
    assert "Анна Соколова" in body
    assert body.startswith("\ufeff") or "code" in body.lower()


def test_owner_users_search(client):
    login(client, "owner@chaihouse.ru", "Owner#2026")
    response = client.get("/owner/users?q=guest@chaihouse.ru")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "guest@chaihouse.ru" in body
    assert "admin@chaihouse.ru" not in body
