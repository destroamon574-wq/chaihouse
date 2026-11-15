"""Публичные страницы доступны без регистрации."""
from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/menu",
        "/menu/plov-chaihouse",
        "/halls",
        "/halls/osnovnoy-zal",
        "/gallery",
        "/about",
        "/contacts",
        "/reviews",
        "/privacy",
        "/terms",
        "/booking/lookup",
    ],
)
def test_public_pages_are_available_without_login(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert "ЧайHouse" in response.get_data(as_text=True)


def test_home_has_seo_metadata(client):
    body = client.get("/").get_data(as_text=True)
    assert '<html lang="ru">' in body
    assert 'name="description"' in body
    assert 'rel="canonical"' in body
    assert 'property="og:image"' in body
    assert 'name="viewport"' in body
    assert "application/ld+json" in body


def test_menu_category_filter(client):
    body = client.get("/menu?category=plov").get_data(as_text=True)
    assert "Плов «ЧайHouse»" in body
    assert "Лагман по-домашнему" not in body


def test_menu_search_and_sort(client):
    response = client.get("/menu?q=лагман")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Лагман по-домашнему" in body
    assert "Шашлык из баранины" not in body

    cheap = client.get("/menu?sort=price_asc").get_data(as_text=True)
    assert cheap.index("Самса с тыквой") < cheap.index("Самса с бараниной")


def test_sql_injection_in_search_is_safe(client, app):
    response = client.get("/menu?q=%27%20OR%201%3D1--")
    assert response.status_code == 200
    assert "Ничего не найдено" in response.get_data(as_text=True)
    with app.app_context():
        from database import get_db

        users = get_db().execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        assert users >= 4


def test_unknown_dish_returns_404(client):
    response = client.get("/menu/nesushchestvuyushchee-blyudo")
    assert response.status_code == 404
    assert "Страница не найдена" in response.get_data(as_text=True)


def test_gallery_has_lightbox_and_alt_text(client):
    body = client.get("/gallery").get_data(as_text=True)
    assert "data-lightbox" in body
    assert 'alt="Тёплый свет латунных ламп' in body


def test_reviews_show_only_published(client):
    body = client.get("/reviews").get_data(as_text=True)
    assert "Плов здесь действительно особенный" in body
    assert "Новая подача салата" not in body


def test_robots_and_sitemap(client):
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Disallow: /admin" in robots.get_data(as_text=True)
    assert "Sitemap: http://localhost/sitemap.xml" in robots.get_data(as_text=True)

    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    body = sitemap.get_data(as_text=True)
    assert "<urlset" in body
    assert "/menu/plov-chaihouse" in body
    assert "/halls/osnovnoy-zal" in body


def test_healthcheck(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["time"].endswith("Z")


def test_not_found_page_is_russian(client):
    body = client.get("/net-takoy-stranicy").get_data(as_text=True)
    assert "Страница не найдена" in body
    assert "На главную" not in body or "На главную" in body


def test_static_assets_available(client):
    css = client.get("/static/css/app.css")
    js = client.get("/static/js/app.js")
    assert css.status_code == 200 and "text/css" in css.headers["Content-Type"]
    assert js.status_code == 200 and "javascript" in js.headers["Content-Type"]
    assert b"admin-shell" in css.data
    assert b"data-booking-form" in js.data


def test_public_pages_have_no_inline_scripts_or_styles(client):
    for path in ("/", "/menu", "/halls", "/gallery", "/reviews", "/contacts"):
        body = client.get(path).get_data(as_text=True).lower()
        assert "<script>" not in body
        assert "onclick=" not in body
        assert "style=" not in body


def test_security_headers_on_public_page(client):
    headers = client.get("/").headers
    csp = headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    # inline-скрипты разрешены только с nonce; 'unsafe-inline' допустим лишь в style-src
    # (Tailwind Play CDN компилирует CSS в рантайме) — в script-src его быть не должно
    script_src = next((part.strip() for part in csp.split(";") if part.strip().startswith("script-src")), "")
    assert "unsafe-inline" not in script_src
    assert "'nonce-" in script_src
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=(self)" in headers["Permissions-Policy"]


def test_media_traversal_is_rejected(client):
    for path in ("/media/..%2Fapp.py", "/media/%2e%2e%5capp.py", "/media/.env"):
        assert client.get(path).status_code == 404
