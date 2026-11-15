"""Общие фикстуры и помощники для pytest."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

import pytest

from app import create_app
from core import reset_rate_limits


def moscow_today() -> date:
    return (datetime.now(timezone.utc) + timedelta(hours=3)).date()


@pytest.fixture
def app(tmp_path):
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


@pytest.fixture(autouse=True)
def _clean_rate_limits():
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture
def client(app):
    return app.test_client()


def extract_csrf(response) -> str:
    body = response.get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', body)
    assert match, "CSRF-токен не найден на странице"
    return match.group(1)


def csrf_for(client, path: str = "/auth/login") -> str:
    response = client.get(path)
    assert response.status_code == 200
    return extract_csrf(response)


def login(client, email: str = "guest@chaihouse.ru", password: str = "Guest#2026"):
    token = csrf_for(client, "/auth/login")
    return client.post(
        "/auth/login",
        data={"csrf_token": token, "email": email, "password": password},
        follow_redirects=False,
    )


def logout(client) -> None:
    page = client.get("/account/")
    if page.status_code == 200:
        token = extract_csrf(page)
        client.post("/auth/logout", data={"csrf_token": token})


def future_date(days: int = 5) -> str:
    return (moscow_today() + timedelta(days=days)).isoformat()


def past_date() -> str:
    return (moscow_today() - timedelta(days=1)).isoformat()


def first_table_id(app, hall_slug: str = "osnovnoy-zal", min_seats: int = 1) -> int:
    from database import get_db

    with app.app_context():
        row = get_db().execute(
            "SELECT t.id FROM dining_tables t JOIN halls h ON h.id = t.hall_id "
            "WHERE h.slug = ? AND t.is_active = 1 AND t.seats >= ? ORDER BY t.seats, t.id LIMIT 1",
            (hall_slug, min_seats),
        ).fetchone()
        assert row, "Не найден подходящий стол"
        return int(row["id"])


def hall_id(app, slug: str = "osnovnoy-zal") -> int:
    from database import get_db

    with app.app_context():
        row = get_db().execute("SELECT id FROM halls WHERE slug = ?", (slug,)).fetchone()
        assert row
        return int(row["id"])
