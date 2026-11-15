"""Админ-панель: брони, меню, залы, галерея, отзывы и журнал."""

from __future__ import annotations

import io

from conftest import csrf_for, extract_csrf, login

PNG_1PX = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00"
    b"\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

DISH_FORM = {
    "name": "Тестовый чай",
    "slug": "testovyy-chay",
    "category_id": "1",
    "price": "350",
    "short_description": "Чай с тестовым ароматом",
    "description": "Чёрный чай с добавлением тестового аромата для проверки формы.",
    "weight": "600 мл",
    "calories": "60",
    "allergens": "—",
    "sort_order": "1",
    "is_active": "1",
    "image_preset": "img/dish-tea.svg",
}


def _db_row(app, sql: str, params=()):
    with app.app_context():
        from database import get_db

        return get_db().execute(sql, params).fetchone()


def test_admin_pages_open_for_admin(client):
    login(client, "admin@chaihouse.ru", "Admin#2026")
    for path in (
        "/admin/",
        "/admin/bookings",
        "/admin/menu",
        "/admin/menu/new",
        "/admin/halls",
        "/admin/gallery",
        "/admin/reviews",
        "/admin/audit",
    ):
        response = client.get(path)
        assert response.status_code == 200, path


def test_admin_booking_status_transition(client, app):
    login(client, "admin@chaihouse.ru", "Admin#2026")
    row = _db_row(app, "SELECT id, status FROM bookings WHERE code = 'CH-DEMO02'")
    token = extract_csrf(client.get(f"/admin/bookings/{row['id']}"))

    response = client.post(
        f"/admin/bookings/{row['id']}/status",
        data={"csrf_token": token, "status": "confirmed", "reason": "Подтверждено по телефону"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    updated = _db_row(app, "SELECT status, cancel_reason FROM bookings WHERE id = ?", (row["id"],))
    assert updated["status"] == "confirmed"
    assert updated["cancel_reason"] == "Подтверждено по телефону"


def test_admin_invalid_status_transition_is_blocked(client, app):
    login(client, "admin@chaihouse.ru", "Admin#2026")
    row = _db_row(app, "SELECT id FROM bookings WHERE code = 'CH-DEMO05'")
    token = extract_csrf(client.get(f"/admin/bookings/{row['id']}"))

    response = client.post(
        f"/admin/bookings/{row['id']}/status",
        data={"csrf_token": token, "status": "completed"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "недоступен" in response.get_data(as_text=True).lower()
    assert _db_row(app, "SELECT status FROM bookings WHERE id = ?", (row["id"],))["status"] == "pending"


def test_admin_menu_crud(client, app):
    login(client, "admin@chaihouse.ru", "Admin#2026")
    token = csrf_for(client, "/admin/menu/new")

    created = client.post("/admin/menu/new", data={"csrf_token": token, **DISH_FORM}, follow_redirects=False)
    assert created.status_code == 302
    dish = _db_row(app, "SELECT * FROM dishes WHERE slug = 'testovyy-chay'")
    assert dish is not None
    assert dish["price"] == 350
    assert dish["image"] == "img/dish-tea.svg"

    page = client.get("/admin/menu?q=тестовый")
    assert "Тестовый чай" in page.get_data(as_text=True)

    toggled = client.post(
        f"/admin/menu/{dish['id']}/toggle", data={"csrf_token": token}, follow_redirects=False
    )
    assert toggled.status_code == 302
    assert _db_row(app, "SELECT is_active FROM dishes WHERE id = ?", (dish["id"],))["is_active"] == 0

    edited = client.post(
        f"/admin/menu/{dish['id']}/edit",
        data={
            "csrf_token": token,
            **DISH_FORM,
            "name": "Тестовый чай обновлён",
            "price": "420",
            "image_preset": "",
        },
        follow_redirects=False,
    )
    assert edited.status_code == 302
    updated = _db_row(app, "SELECT name, price FROM dishes WHERE id = ?", (dish["id"],))
    assert updated["name"] == "Тестовый чай обновлён"
    assert updated["price"] == 420

    removed = client.post(
        f"/admin/menu/{dish['id']}/delete", data={"csrf_token": token}, follow_redirects=False
    )
    assert removed.status_code == 302
    assert _db_row(app, "SELECT 1 FROM dishes WHERE id = ?", (dish["id"],)) is None


def test_menu_validation_rejects_duplicate_slug(client):
    login(client, "admin@chaihouse.ru", "Admin#2026")
    token = csrf_for(client, "/admin/menu/new")
    response = client.post(
        "/admin/menu/new",
        data={"csrf_token": token, **DISH_FORM, "slug": "plov-chaihouse"},
    )
    assert response.status_code == 200
    assert "уже занят" in response.get_data(as_text=True)


def test_admin_can_add_and_toggle_table(client, app):
    login(client, "admin@chaihouse.ru", "Admin#2026")
    token = csrf_for(client, "/admin/halls")

    added = client.post(
        "/admin/halls/1/tables",
        data={"csrf_token": token, "name": "Стол 99", "seats": "6"},
        follow_redirects=False,
    )
    assert added.status_code == 302
    table = _db_row(app, "SELECT * FROM dining_tables WHERE name = 'Стол 99'")
    assert table is not None and table["seats"] == 6

    client.post(f"/admin/tables/{table['id']}/toggle", data={"csrf_token": token})
    assert _db_row(app, "SELECT is_active FROM dining_tables WHERE id = ?", (table["id"],))["is_active"] == 0


def test_admin_can_hide_and_restore_hall(client, app):
    login(client, "admin@chaihouse.ru", "Admin#2026")
    token = csrf_for(client, "/admin/halls")

    client.post("/admin/halls/1/toggle", data={"csrf_token": token})
    assert _db_row(app, "SELECT is_active FROM halls WHERE id = 1")["is_active"] == 0
    assert "/halls/osnovnoy-zal" not in client.get("/halls").get_data(as_text=True)

    client.post("/admin/halls/1/toggle", data={"csrf_token": token})
    assert _db_row(app, "SELECT is_active FROM halls WHERE id = 1")["is_active"] == 1
    assert "/halls/osnovnoy-zal" in client.get("/halls").get_data(as_text=True)


def test_admin_gallery_preset_and_delete(client, app):
    login(client, "admin@chaihouse.ru", "Admin#2026")
    token = csrf_for(client, "/admin/gallery")

    added = client.post(
        "/admin/gallery",
        data={
            "csrf_token": token,
            "title": "Тестовый свет",
            "alt": "Лампы над тестовым столом",
            "category": "details",
            "image_preset": "img/detail-lamp.svg",
        },
        follow_redirects=False,
    )
    assert added.status_code == 302
    item = _db_row(app, "SELECT * FROM gallery_images WHERE title = 'Тестовый свет'")
    assert item is not None and item["category"] == "details"
    assert "Тестовый свет" in client.get("/gallery").get_data(as_text=True)

    client.post(f"/admin/gallery/{item['id']}/delete", data={"csrf_token": token})
    assert _db_row(app, "SELECT 1 FROM gallery_images WHERE id = ?", (item["id"],)) is None


def test_admin_upload_accepts_png_and_stores_random_name(client, app):
    login(client, "admin@chaihouse.ru", "Admin#2026")
    token = csrf_for(client, "/admin/gallery")

    added = client.post(
        "/admin/gallery",
        data={
            "csrf_token": token,
            "title": "Загруженное фото",
            "alt": "Загруженная тестовая фотография",
            "category": "interior",
            "image_file": (io.BytesIO(PNG_1PX), "tiny.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert added.status_code == 302
    item = _db_row(app, "SELECT * FROM gallery_images WHERE title = 'Загруженное фото'")
    assert item is not None
    assert item["image"].startswith("uploads/")
    assert "tiny" not in item["image"]

    saved = client.get("/" + item["image"].replace("uploads/", "media/"))
    assert saved.status_code == 200


def test_admin_upload_rejects_executable_file(client, app):
    login(client, "admin@chaihouse.ru", "Admin#2026")
    token = csrf_for(client, "/admin/gallery")
    response = client.post(
        "/admin/gallery",
        data={
            "csrf_token": token,
            "title": "Опасный файл",
            "alt": "Файл, который не должен загрузиться",
            "category": "interior",
            "image_file": (io.BytesIO(b"<?php echo 1; ?>"), "shell.php"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert "PNG" in response.get_data(as_text=True)
    assert _db_row(app, "SELECT 1 FROM gallery_images WHERE title = 'Опасный файл'") is None


def test_admin_review_moderation_publish_save_and_reject(client, app):
    login(client, "admin@chaihouse.ru", "Admin#2026")
    pending = _db_row(app, "SELECT id FROM reviews WHERE status = 'pending' LIMIT 1")
    token = csrf_for(client, "/admin/reviews?status=pending")

    saved = client.post(
        f"/admin/reviews/{pending['id']}/moderate",
        data={"csrf_token": token, "action": "save", "reply": "Спасибо за отзыв!"},
        follow_redirects=False,
    )
    assert saved.status_code == 302
    row = _db_row(app, "SELECT status, admin_reply FROM reviews WHERE id = ?", (pending["id"],))
    assert row["status"] == "pending"
    assert row["admin_reply"] == "Спасибо за отзыв!"

    published = client.post(
        f"/admin/reviews/{pending['id']}/moderate",
        data={"csrf_token": token, "action": "publish", "reply": "Спасибо за отзыв!"},
        follow_redirects=False,
    )
    assert published.status_code == 302
    assert _db_row(app, "SELECT status FROM reviews WHERE id = ?", (pending["id"],))["status"] == "published"
    assert "Спасибо за отзыв!" in client.get("/reviews").get_data(as_text=True)

    rejected = client.post(
        f"/admin/reviews/{pending['id']}/moderate",
        data={"csrf_token": token, "action": "reject", "reply": ""},
        follow_redirects=False,
    )
    assert rejected.status_code == 302
    assert _db_row(app, "SELECT status FROM reviews WHERE id = ?", (pending["id"],))["status"] == "rejected"


def test_audit_log_records_actions(client):
    login(client, "admin@chaihouse.ru", "Admin#2026")
    token = csrf_for(client, "/admin/menu/new")
    client.post("/admin/menu/new", data={"csrf_token": token, **DISH_FORM, "slug": "audit-test-chay"})

    body = client.get("/admin/audit").get_data(as_text=True)
    assert "dish.created" in body
    assert "audit-test-chay" in body or "Тестовый чай" in body


def test_admin_search_sql_injection_is_safe(client):
    login(client, "admin@chaihouse.ru", "Admin#2026")
    response = client.get("/admin/bookings?q=%27%20OR%201%3D1--")
    assert response.status_code == 200
    assert "Найдено" in response.get_data(as_text=True)
