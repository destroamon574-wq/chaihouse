"""Безопасность: CSRF, XSS, инъекции, заголовки и загрузки."""
from __future__ import annotations

import io
import re

from conftest import csrf_for, extract_csrf, login


def _csp_directive(csp: str, name: str) -> str:
    """Возвращает директиву CSP по имени (например, script-src)."""
    for part in csp.split(";"):
        parts = part.strip().split()
        if parts and parts[0] == name:
            return " ".join(parts)
    return ""


def _row(app, sql: str, params=()):
    with app.app_context():
        from database import get_db

        return get_db().execute(sql, params).fetchone()


def test_admin_post_without_csrf_is_rejected(client):
    login(client, "admin@chaihouse.ru", "Admin#2026")
    response = client.post("/admin/menu/1/toggle")
    assert response.status_code == 400
    assert "CSRF" in response.get_data(as_text=True)


def test_account_post_without_csrf_is_rejected(client):
    login(client)
    response = client.post("/account/notifications/read-all")
    assert response.status_code == 400


def test_review_text_is_escaped_on_public_page(client, app):
    reviewer = app.test_client()
    login(reviewer)
    token = extract_csrf(reviewer.get("/reviews"))
    payload = '<script>alert("xss")</script> Плов был очень вкусным'
    reviewer.post("/reviews", data={"csrf_token": token, "rating": "5", "text": payload},
                  follow_redirects=False)

    review = _row(app, "SELECT id FROM reviews ORDER BY id DESC LIMIT 1")
    admin = app.test_client()
    login(admin, "admin@chaihouse.ru", "Admin#2026")
    admin_token = csrf_for(admin, "/admin/reviews?status=pending")
    admin.post(f"/admin/reviews/{review['id']}/moderate",
               data={"csrf_token": admin_token, "action": "publish", "reply": ""})

    body = client.get("/reviews").get_data(as_text=True)
    assert '<script>alert("xss")</script>' not in body
    assert "&lt;script&gt;" in body


def test_booking_status_xss_in_reason_is_escaped(client, app):
    login(client, "admin@chaihouse.ru", "Admin#2026")
    row = _row(app, "SELECT id FROM bookings WHERE code = 'CH-DEMO01'")
    token = extract_csrf(client.get(f"/admin/bookings/{row['id']}"))
    client.post(
        f"/admin/bookings/{row['id']}/status",
        data={"csrf_token": token, "status": "cancelled",
              "reason": "<img src=x onerror=alert(1)>"},
        follow_redirects=False,
    )
    page = client.get("/booking/success/CH-DEMO01")
    body = page.get_data(as_text=True)
    assert "<img src=x onerror=alert(1)>" not in body
    assert "&lt;img" in body


def test_lookup_sql_injection_is_safe(client):
    token = csrf_for(client, "/booking/lookup")
    response = client.post(
        "/booking/lookup",
        data={"csrf_token": token, "code": "' OR 1=1--", "phone": "+79990000000"},
    )
    assert response.status_code == 200
    assert "не найдена" in response.get_data(as_text=True)


def test_security_headers_on_private_pages(client):
    login(client, "owner@chaihouse.ru", "Owner#2026")
    response = client.get("/owner/")
    csp = response.headers["Content-Security-Policy"]
    # inline-скрипты запрещены: разрешён только nonce (см. app.py)
    assert "'unsafe-inline'" not in _csp_directive(csp, "script-src")
    assert re.search(r"script-src[^;]*'nonce-", csp), "script-src должен использовать nonce"
    assert "frame-ancestors 'none'" in csp
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    body = response.get_data(as_text=True)
    assert 'content="noindex, nofollow"' in body


def test_session_cookie_is_protected(client):
    token = csrf_for(client, "/auth/login")
    response = client.post(
        "/auth/login",
        data={"csrf_token": token, "email": "guest@chaihouse.ru", "password": "Guest#2026"},
        follow_redirects=False,
    )
    cookies = response.headers.getlist("Set-Cookie")
    session_cookie = next((value for value in cookies if value.startswith("session=")), "")
    assert session_cookie
    assert "HttpOnly" in session_cookie
    assert "SameSite=Lax" in session_cookie or "SameSite=Strict" in session_cookie


def test_password_hashes_are_not_plaintext(app):
    row = _row(app, "SELECT password_hash FROM users WHERE email = 'guest@chaihouse.ru'")
    assert row["password_hash"] != "Guest#2026"
    assert row["password_hash"].startswith("scrypt:") or len(row["password_hash"]) > 40


def test_upload_with_fake_png_signature_is_rejected(client, app):
    login(client, "admin@chaihouse.ru", "Admin#2026")
    token = csrf_for(client, "/admin/gallery")
    response = client.post(
        "/admin/gallery",
        data={
            "csrf_token": token,
            "title": "Поддельная картинка",
            "alt": "Файл с поддельной сигнатурой",
            "category": "interior",
            "image_file": (io.BytesIO(b"<?php echo 'hack'; ?>"), "fake.png"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert "не похоже" in response.get_data(as_text=True)
    assert _row(app, "SELECT 1 FROM gallery_images WHERE title = 'Поддельная картинка'") is None


def test_private_pages_are_not_indexed(client):
    login(client)
    body = client.get("/account/").get_data(as_text=True)
    assert 'content="noindex, nofollow"' in body
    assert 'rel="canonical"' not in body


def test_robots_disallows_private_sections(client):
    body = client.get("/robots.txt").get_data(as_text=True)
    for section in ("/admin", "/owner", "/account", "/auth", "/booking"):
        assert f"Disallow: {section}" in body
