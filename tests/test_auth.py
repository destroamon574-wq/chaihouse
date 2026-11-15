"""Аутентификация, регистрация и роли."""
from __future__ import annotations

from conftest import csrf_for, extract_csrf, login


def test_anonymous_account_and_admin_redirect_to_login(client):
    for path in ("/account/", "/account/bookings", "/admin/", "/owner/"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["Location"].startswith("/auth/login")


def test_login_with_demo_guest(client):
    response = login(client)
    assert response.status_code == 302
    assert response.headers["Location"] == "/account/"
    page = client.get("/account/")
    assert page.status_code == 200
    assert "Анна" in page.get_data(as_text=True)


def test_login_with_wrong_password(client):
    token = csrf_for(client, "/auth/login")
    response = client.post(
        "/auth/login",
        data={"csrf_token": token, "email": "guest@chaihouse.ru", "password": "Wrong#2026"},
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert "Неверный email или пароль" in response.get_data(as_text=True)


def test_login_with_sql_injection_email(client):
    token = csrf_for(client, "/auth/login")
    response = client.post(
        "/auth/login",
        data={"csrf_token": token, "email": "' OR 1=1--", "password": "whatever1"},
        follow_redirects=False,
    )
    assert response.status_code == 401


def test_register_new_guest(client, app):
    token = csrf_for(client, "/auth/register")
    response = client.post(
        "/auth/register",
        data={
            "csrf_token": token,
            "name": "Тестовый Гость",
            "email": "new.guest@example.com",
            "phone": "+79990009999",
            "password": "TestPass123",
            "password2": "TestPass123",
            "consent": "1",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/account/"
    with app.app_context():
        from database import get_db

        row = get_db().execute("SELECT * FROM users WHERE email = ?", ("new.guest@example.com",)).fetchone()
        assert row is not None
        assert row["role"] == "guest"
        assert row["password_hash"] != "TestPass123"


def test_registration_next_returns_to_booking(client):
    token = csrf_for(client, "/auth/register?next=/booking")
    response = client.post(
        "/auth/register?next=/booking",
        data={
            "csrf_token": token,
            "name": "Будущий Гость",
            "email": "booking.guest@example.com",
            "password": "TestPass123",
            "password2": "TestPass123",
            "consent": "1",
            "next": "/booking",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/booking"


def test_registration_rejects_duplicate_email_and_weak_password(client):
    token = csrf_for(client, "/auth/register")
    response = client.post(
        "/auth/register",
        data={
            "csrf_token": token,
            "name": "Дубль",
            "email": "guest@chaihouse.ru",
            "password": "123",
            "password2": "123",
            "consent": "1",
        },
    )
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "уже зарегистрирован" in body
    assert "минимум 8 символов" in body


def test_registration_requires_consent(client):
    token = csrf_for(client, "/auth/register")
    response = client.post(
        "/auth/register",
        data={
            "csrf_token": token,
            "name": "Без Согласия",
            "email": "no-consent@example.com",
            "password": "TestPass123",
            "password2": "TestPass123",
        },
    )
    assert response.status_code == 200
    assert "согласи" in response.get_data(as_text=True).lower()


def test_roles_are_separated(client):
    login(client, "admin@chaihouse.ru", "Admin#2026")
    assert client.get("/admin/").status_code == 200
    assert client.get("/owner/").status_code == 403


def test_guest_cannot_open_admin(client):
    login(client)
    assert client.get("/admin/").status_code == 403


def test_owner_can_open_admin_and_owner_panels(client):
    login(client, "owner@chaihouse.ru", "Owner#2026")
    assert client.get("/admin/").status_code == 200
    assert client.get("/owner/").status_code == 200


def test_login_open_redirect_is_blocked(client):
    token = csrf_for(client, "/auth/login")
    response = client.post(
        "/auth/login",
        data={
            "csrf_token": token,
            "email": "guest@chaihouse.ru",
            "password": "Guest#2026",
            "next": "https://evil.example/phish",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/account/"


def test_login_rate_limit(client):
    for _ in range(5):
        token = csrf_for(client, "/auth/login")
        client.post(
            "/auth/login",
            data={"csrf_token": token, "email": "guest@chaihouse.ru", "password": "bad-pass1"},
        )
    token = csrf_for(client, "/auth/login")
    response = client.post(
        "/auth/login",
        data={"csrf_token": token, "email": "guest@chaihouse.ru", "password": "Guest#2026"},
    )
    assert response.status_code == 429
    assert "Слишком много попыток" in response.get_data(as_text=True)


def test_post_without_csrf_is_rejected(client):
    response = client.post("/auth/login", data={"email": "guest@chaihouse.ru", "password": "Guest#2026"})
    assert response.status_code == 400
    assert "CSRF" in response.get_data(as_text=True)


def test_logout_clears_session(client):
    login(client)
    token = extract_csrf(client.get("/account/"))
    client.post("/auth/logout", data={"csrf_token": token})
    response = client.get("/account/", follow_redirects=False)
    assert response.status_code == 302


def test_password_change_invalidates_other_sessions(client, app):
    other = app.test_client()
    login(client)
    login(other)

    token = extract_csrf(client.get("/account/settings"))
    response = client.post(
        "/account/password",
        data={"csrf_token": token, "current": "Guest#2026", "password": "NewGuest#2026", "password2": "NewGuest#2026"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert client.get("/account/").status_code == 200
    assert other.get("/account/", follow_redirects=False).status_code == 302


def test_forgot_password_demo_shows_reset_link(client):
    token = csrf_for(client, "/auth/forgot-password")
    response = client.post(
        "/auth/forgot-password",
        data={"csrf_token": token, "email": "guest@chaihouse.ru"},
    )
    assert response.status_code == 200
    assert "/auth/reset-password/" in response.get_data(as_text=True)
