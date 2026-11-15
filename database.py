"""Подключение к SQLite, миграции и демонстрационные данные."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import click
from flask import current_app, g

from core import BASE_DIR, hash_password, utc_stamp

SCHEMA_VERSION = 2
SCHEMA_PATH = BASE_DIR / "schema.sql"


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        path = Path(current_app.config["DATABASE_PATH"])
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(path), timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.create_function(
            "py_lower", 1,
            lambda value: value.lower() if isinstance(value, str) else value,
            deterministic=True,
        )
        g.db = connection
    return g.db


def close_db(_exception=None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db() -> None:
    db = get_db()
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    db.executescript(schema_sql)
    _migrate(db)
    db.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
        (SCHEMA_VERSION, utc_stamp()),
    )
    db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    db.commit()
    if current_app.config.get("AUTO_SEED", True):
        seed_db(db)


def _migrate(db: sqlite3.Connection) -> None:
    """Пошаговые миграции для существующих баз: аккуратно добавляем новые колонки."""
    columns = {row["name"] for row in db.execute("PRAGMA table_info(bookings)").fetchall()}
    if "reminded_at" not in columns:
        db.execute("ALTER TABLE bookings ADD COLUMN reminded_at TEXT")


def seed_db(db: sqlite3.Connection, force: bool = False) -> bool:
    """Идемпотентно заполняет пустую БД демо-данными."""
    existing = db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    if existing and not force:
        return False
    if force:
        for table in (
            "audit_log", "notifications", "favorites", "reviews", "bookings",
            "gallery_images", "dishes", "menu_categories", "dining_tables",
            "halls", "password_resets", "settings", "users",
        ):
            db.execute(f"DELETE FROM {table}")

    now = utc_stamp()
    users = [
        ("Алишер Рахимов", "owner@chaihouse.ru", "+79991204518", "Owner#2026", "owner"),
        ("Мадина Каримова", "admin@chaihouse.ru", "+79991204519", "Admin#2026", "admin"),
        ("Анна Соколова", "guest@chaihouse.ru", "+79990001122", "Guest#2026", "guest"),
        ("Игорь Лебедев", "igor@example.com", "+79990003344", "Guest#2026", "guest"),
    ]
    for name, email, phone, password, role in users:
        db.execute(
            "INSERT INTO users(name, email, phone, password_hash, role, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, email, phone, hash_password(password), role, now, now),
        )

    halls = [
        (
            "osnovnoy-zal", "Основной зал", "Тёплый свет, резные узоры и большие компании",
            "Главный зал ресторана: тёмное дерево, латунные светильники с бахромой и мягкие "
            "диваны с бирюзовым узором. Здесь хорошо и на свидании за столиком у окна, и "
            "большой семьёй за длинным столом. По пятницам играет живая музыка.",
            60, 0, "img/hall-main.svg",
            '["Живая музыка по пятницам", "Столы на 2–10 гостей", "Детские стулья"]', 1,
        ),
        (
            "veranda", "Веранда", "Свет, зелень и вид на город",
            "Светлый зал с панорамными окнами, лёгкими шторами и растениями. Днём здесь "
            "особенно приятно пить чай с самсой, а вечером — наблюдать, как зажигаются "
            "огни города.",
            30, 0, "img/hall-veranda.svg",
            '["Панорамные окна", "Тихое место", "Подходит для завтраков и чаепитий"]', 2,
        ),
        (
            "vip", "VIP-зал", "Отдельная комната для своих",
            "Закрытый зал с синими узорчатыми стенами, мозаичными лампами и длинным столом "
            "из светлого дерева. Свой звук, экран и персональный официант — для дней "
            "рождения, переговоров и семейных вечеров.",
            12, 15000, "img/hall-vip.svg",
            '["Отдельная комната", "Свой звук и экран", "Персональный официант"]', 3,
        ),
        (
            "banquet", "Банкетный зал", "Длинный стол и место для праздника",
            "Просторный зал с деревянными балками, красными банкетками и длинным столом, "
            "который собирают под вашу компанию. Поможем с меню, декором и сценарием вечера.",
            40, 30000, "img/hall-banquet.svg",
            '["Банкеты до 40 гостей", "Место для ведущего", "Свой сценарий вечера"]', 4,
        ),
    ]
    for hall in halls:
        db.execute(
            "INSERT INTO halls(slug, name, tagline, description, capacity, min_spend, image, "
            "features, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            hall,
        )

    tables = {
        "osnovnoy-zal": [("Стол 1", 2), ("Стол 2", 2), ("Стол 3", 4), ("Стол 4", 4),
                          ("Стол 5", 6), ("Стол 6", 6), ("Стол 7", 8), ("Стол 8", 10)],
        "veranda": [("Веранда 1", 2), ("Веранда 2", 4), ("Веранда 3", 4),
                    ("Веранда 4", 6), ("Веранда 5", 8)],
        "vip": [("VIP 1", 6), ("VIP 2", 8)],
        "banquet": [("Банкет 1", 10), ("Банкет 2", 12), ("Банкет 3", 18)],
    }
    hall_ids = {
        row["slug"]: row["id"] for row in db.execute("SELECT id, slug FROM halls").fetchall()
    }
    for hall_slug, items in tables.items():
        for name, seats in items:
            db.execute(
                "INSERT INTO dining_tables(hall_id, name, seats) VALUES (?, ?, ?)",
                (hall_ids[hall_slug], name, seats),
            )

    categories = [
        ("plov", "Плов и каши", "Рассчитан на неспешную трапезу и большую компанию", 1),
        ("soups", "Лагман и супы", "Горячие бульоны и тянутая лапша", 2),
        ("manti", "Манты и пельмени", "Тонкое тесто, сочная начинка, пар", 3),
        ("grill", "Шашлык и кебабы", "Мангал, дым и восточные специи", 4),
        ("salads", "Салаты и закуски", "Свежие овощи, зелень и жареные баклажаны", 5),
        ("bakery", "Выпечка", "Самса из тандыра — к чаю и разговору", 6),
        ("tea", "Чай и напитки", "Согревающие чаи и домашние морсы", 7),
    ]
    for slug, name, description, sort_order in categories:
        db.execute(
            "INSERT INTO menu_categories(slug, name, description, sort_order) VALUES (?, ?, ?, ?)",
            (slug, name, description, sort_order),
        )
    category_ids = {
        row["slug"]: row["id"] for row in db.execute("SELECT id, slug FROM menu_categories").fetchall()
    }

    dishes = [
        ("plov-chaihouse", "plov", "Плов «ЧайHouse»",
         "Баранина, рис лазер, жёлтая морковь и целый чеснок",
         "Готовим в казане на живом огне: рис лазер, баранина, жёлтая морковь, "
         "кумин и целая головка чеснока. Подаём с ачичуком и свежей лепёшкой. "
         "Это блюдо лучше заказывать на компанию — и обязательно заранее.",
         690, "450 г", 780, "Глютен (лепёшка)", "img/dish-plov.svg", 0, 0, 1, 1),
        ("plov-lamb", "plov", "Плов с бараниной",
         "Классический ташкентский плов из казана",
         "Рассыпчатый рис, тушёная баранина, морковь и зира. Подаём с маринованным "
         "луком и лепёшкой.",
         790, "450 г", 820, "Глютен (лепёшка)", "img/dish-plov.svg", 0, 0, 0, 2),
        ("plov-chicken", "plov", "Плов с курицей",
         "Более лёгкий вариант — с куриным бедром и овощами",
         "Плов на курином бульоне с морковью, луком и специями. Мягкий вкус, "
         "который нравится и детям, и тем, кто выбирает птицу.",
         590, "420 г", 690, "Глютен (лепёшка)", "img/dish-plov.svg", 0, 0, 0, 3),
        ("lagman", "soups", "Лагман по-домашнему",
         "Тянутая лапша, говядина, джусай и овощи",
         "Тесто для лапши раскатываем и вытягиваем вручную. В бульоне — говядина, "
         "болгарский перец, джусай и специи. Подаём с ложкой острого соуса отдельно.",
         560, "400 г", 520, "Глютен, яйцо", "img/dish-lagman.svg", 0, 0, 1, 1),
        ("shurpa", "soups", "Шурпа из баранины",
         "Наваристый бульон с крупными кусками мяса и овощами",
         "Варим шесть часов: баранина на кости, картофель, морковь, помидоры и зелень. "
         "Сытный суп, после которого хочется остаться подольше.",
         520, "400 г", 460, "Сельдерей", "img/dish-shurpa.svg", 0, 0, 0, 2),
        ("mastava", "soups", "Мастава с говядиной",
         "Рис, овощи и томатный бульон",
         "Лёгкий томатный суп с рисом, говядиной и овощами. Подаём со сметаной "
         "и зеленью.",
         490, "350 г", 380, "Молочные продукты", "img/dish-shurpa.svg", 0, 0, 0, 3),
        ("manti-lamb", "manti", "Манты с бараниной",
         "Шесть мантов на пару, с курдюком и луком",
         "Тонкое тесто, рубленая баранина, курдюк и много лука. Готовим на пару "
         "и подаём со сметаной и томатным соусом.",
         520, "6 шт · 360 г", 610, "Глютен, молочные продукты", "img/dish-manti.svg", 0, 0, 0, 1),
        ("manti-pumpkin", "manti", "Манты с тыквой",
         "Вегетарианские манты с тыквой и луком",
         "Сладковатая тыква, лук и зира в тонком тесте. Подаём со сметаной "
         "или с острым томатным соусом.",
         450, "6 шт · 340 г", 420, "Глютен, молочные продукты", "img/dish-manti.svg", 1, 0, 0, 2),
        ("chuchvara", "manti", "Чучвара",
         "Маленькие пельмени в бульоне с зеленью",
         "Говядина и лук в тонком тесте, бульон с помидорами и зеленью. "
         "Подаём в керамической пиале.",
         480, "300 г", 450, "Глютен, яйцо", "img/dish-manti.svg", 0, 0, 0, 3),
        ("shashlik-lamb", "grill", "Шашлык из баранины",
         "Мякоть баранины на углях, с луком и аджикой",
         "Маринуем баранину в луке и специях, готовим на живых углях. Подаём "
         "с маринованным луком, зеленью и домашней аджикой.",
         720, "250 г", 640, "Горчица", "img/dish-shashlik.svg", 0, 0, 1, 1),
        ("shashlik-chicken", "grill", "Шашлык из курицы",
         "Куриное бедро в йогуртовом маринаде",
         "Сочное куриное бедро в маринаде из йогурта, чеснока и паприки. "
         "Подаём с печёными овощами.",
         540, "250 г", 480, "Молочные продукты", "img/dish-shashlik.svg", 0, 0, 0, 2),
        ("lula-kebab", "grill", "Люля-кебаб",
         "Рубленая баранина с луком и зеленью",
         "Баранина и лук, рубленные вручную, на плоском шампуре. Подаём с лавашом, "
         "сумахом и томатным соусом.",
         590, "230 г", 560, "Глютен", "img/dish-kebab.svg", 0, 0, 0, 3),
        ("beef-kebab", "grill", "Кебаб из говядины",
         "Мраморная говядина, перец и лук на углях",
         "Крупные куски говядины, болгарский перец и красный лук. Готовим "
         "до средней прожарки, подаём с соусом из печёного перца.",
         650, "230 г", 590, "—", "img/dish-kebab.svg", 0, 0, 0, 4),
        ("eggplant-salad", "salads", "Салат из жареных баклажанов",
         "Баклажаны на гриле, томаты, кинза и гранат",
         "Баклажаны обжариваем на гриле, добавляем томаты, красный лук, кинзу, "
         "чеснок и зёрна граната. Одно из тех блюд, за которыми возвращаются.",
         420, "220 г", 240, "—", "img/dish-eggplant.svg", 1, 0, 1, 1),
        ("achichuk", "salads", "Ачичук",
         "Тонко нарезанные томаты, лук и перец",
         "Свежие томаты, красный лук, острый перец и зелень. Просто, свежо "
         "и очень к месту рядом с пловом.",
         320, "200 г", 90, "—", "img/dish-achichuk.svg", 1, 1, 0, 2),
        ("tashkent-salad", "salads", "Ташкентский салат",
         "Редис, томаты, огурцы и жареный лук",
         "Хрустящие овощи, редис и жареный лук под лёгкой заправкой из йогурта. "
         "Освежает после шашлыка.",
         380, "220 г", 150, "Молочные продукты", "img/dish-achichuk.svg", 1, 0, 0, 3),
        ("samsa-lamb", "bakery", "Самса с бараниной",
         "Одна самса из тандыра, с курдюком и луком",
         "Слоёное тесто, рубленая баранина, курдюк и лук. Печём в тандыре "
         "до хрустящей корочки. Подаём горячей.",
         250, "1 шт · 110 г", 310, "Глютен", "img/dish-samsa.svg", 0, 0, 0, 1),
        ("samsa-pumpkin", "bakery", "Самса с тыквой",
         "Сладковатая тыква, лук и кунжут",
         "Вегетарианская самса с тыквой, луком и кунжутом. Хороша к чаю "
         "с чабрецом.",
         220, "1 шт · 105 г", 270, "Глютен, кунжут", "img/dish-samsa.svg", 1, 0, 0, 2),
        ("tea-thyme", "tea", "Чай с чабрецом",
         "Чайник 600 мл, чёрный чай и горный чабрец",
         "Крепкий чёрный чай с чабрецом и мёдом. Подаём в чайнике с пиалами — "
         "как принято за неспешным разговором.",
         390, "600 мл", 60, "Мёд", "img/dish-tea.svg", 1, 0, 0, 1),
        ("tea-dried-fruits", "tea", "Восточный чай с сухофруктами",
         "Чайник 700 мл, курага, изюм и специи",
         "Чёрный чай, курага, изюм, палочка корицы и немного апельсиновой цедры. "
         "Согревающий и совсем не приторный.",
         450, "700 мл", 90, "—", "img/dish-tea.svg", 1, 0, 1, 2),
        ("sea-buckthorn", "tea", "Облепиховый морс",
         "Домашний морс из облепихи с апельсином",
         "Облепиха, апельсин и немного мёда. Кисло-сладкий, яркий и очень "
         "кстати в холодный вечер.",
         290, "300 мл", 110, "Мёд", "img/dish-kompot.svg", 1, 0, 0, 3),
    ]
    for dish in dishes:
        (slug, cat_slug, name, short, description, price, weight, calories,
         allergens, image, vegetarian, spicy, signature, sort_order) = dish
        db.execute(
            "INSERT INTO dishes(category_id, slug, name, short_description, description, price, "
            "weight, calories, allergens, image, is_vegetarian, is_spicy, is_signature, "
            "sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (category_ids[cat_slug], slug, name, short, description, price, weight, calories,
             allergens, image, vegetarian, spicy, signature, sort_order, now, now),
        )

    gallery = [
        ("Основной зал вечером", "Тёплый свет латунных ламп и бирюзовые диваны в основном зале",
         "img/hero-interior.svg", "interior", 1),
        ("Столы у окна", "Сервировка и мягкие кресла в основном зале", "img/hall-main.svg",
         "interior", 2),
        ("VIP-зал", "Синие узорчатые стены и длинный стол в VIP-зале", "img/hall-vip.svg",
         "interior", 3),
        ("Банкетный зал", "Длинный стол с красными банкетками", "img/hall-banquet.svg",
         "interior", 4),
        ("Веранда днём", "Светлые шторы и зелень на веранде", "img/hall-veranda.svg",
         "interior", 5),
        ("Латунный свет", "Резной абажур с бахромой крупным планом", "img/detail-lamp.svg",
         "details", 6),
        ("Узор на потолке", "Геометрический латунный узор под потолком", "img/detail-ornament.svg",
         "details", 7),
        ("Сервировка", "Льняная салфетка, приборы и хрустальный бокал", "img/detail-table.svg",
         "details", 8),
        ("Плов «ЧайHouse»", "Фирменный плов с бараниной и чесноком", "img/dish-plov.svg",
         "food", 9),
        ("Салат из баклажанов", "Жареные баклажаны с томатами и гранатом", "img/dish-eggplant.svg",
         "food", 10),
        ("Чай с чабрецом", "Чайник чая с пиалами на деревянном столе", "img/dish-tea.svg",
         "food", 11),
    ]
    for title, alt, image, category, sort_order in gallery:
        db.execute(
            "INSERT INTO gallery_images(title, alt, image, category, sort_order, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (title, alt, image, category, sort_order, now),
        )

    reviews = [
        (3, "Анна Соколова", 5,
         "Плов здесь действительно особенный: рассыпчатый, с мягкой бараниной и очень "
         "ароматным чесноком. Сидели в основном зале — свет ламп и узоры на потолке "
         "делают вечер каким-то очень тёплым.", "published", "Спасибо, Анна! Передали "
         "комплимент команде казана.", 10),
        (4, "Игорь Лебедев", 5,
         "Бронировал VIP-зал на день рождения. Помогли с меню, вовремя принесли самсу, "
         "ничего не пришлось напоминать. Отдельное спасибо за чай с сухофруктами.", "published",
         "Рады, что вечер получился! Ждём снова.", 20),
        (3, "Анна Соколова", 4,
         "Лагман с тянутой лапшой — то, за чем стоит вернуться. В пятницу живая музыка, "
         "поэтому если хочется тишины, лучше бронировать веранду.", "published", None, 30),
        (3, "Анна Соколова", 5,
         "Новая подача салата из баклажанов — стало ещё вкуснее.", "pending", None, 40),
    ]
    for user_id, author, rating, text, status, reply, days_ago in reviews:
        created = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
        db.execute(
            "INSERT INTO reviews(user_id, author_name, rating, text, status, admin_reply, "
            "created_at, moderated_by, moderated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, author, rating, text, status, reply, created,
             2 if status != "pending" else None, created if status != "pending" else None),
        )

    table_rows = db.execute(
        "SELECT t.id, t.name, h.slug FROM dining_tables t JOIN halls h ON h.id = t.hall_id"
    ).fetchall()
    table_ids = {(r["slug"], r["name"]): r["id"] for r in table_rows}
    today = date.today()
    bookings = [
        ("CH-DEMO01", 3, "osnovnoy-zal", "Стол 3", "Анна Соколова", "+79990001122",
         "guest@chaihouse.ru", today, "19:00", 19 * 60, 21 * 60, 4, "Ужин",
         "Столик у окна, если возможно.", "confirmed", 1),
        ("CH-DEMO02", None, "osnovnoy-zal", "Стол 5", "Тимур Алиев", "+79995554433",
         None, today, "20:00", 20 * 60, 22 * 60, 6, "Встреча с друзьями",
         None, "pending", 2),
        ("CH-DEMO03", 4, "veranda", "Веранда 3", "Игорь Лебедев", "+79990003344",
         "igor@example.com", today + timedelta(days=1), "18:00", 18 * 60, 20 * 60, 4,
         "Свидание", "Тихий стол у окна.", "confirmed", 3),
        ("CH-DEMO04", 4, "vip", "VIP 2", "Игорь Лебедев", "+79990003344",
         "igor@example.com", today + timedelta(days=2), "19:00", 19 * 60, 21 * 60, 8,
         "День рождения", "Нужен торт со свечами к 21:00.", "confirmed", 4),
        ("CH-DEMO05", None, "banquet", "Банкет 1", "Мария Ветрова", "+79997778899",
         None, today + timedelta(days=3), "18:00", 18 * 60, 22 * 60, 10,
         "Корпоратив", None, "pending", 5),
        ("CH-DEMO06", 3, "osnovnoy-zal", "Стол 6", "Анна Соколова", "+79990001122",
         "guest@chaihouse.ru", today - timedelta(days=1), "20:00", 20 * 60, 22 * 60, 2,
         "Ужин", None, "completed", 6),
    ]
    for (code, user_id, hall_slug, table_name, name, phone, email, bdate, time_value,
         start_min, end_min, guests, occasion, comment, status, days_ago) in bookings:
        created = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
        db.execute(
            "INSERT INTO bookings(code, user_id, hall_id, table_id, guest_name, guest_phone, "
            "guest_email, date, time, start_min, end_min, guests_count, occasion, comment, "
            "status, created_at, updated_at, confirmed_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (code, user_id, hall_ids[hall_slug], table_ids[(hall_slug, table_name)], name, phone,
             email, bdate.isoformat(), time_value, start_min, end_min, guests, occasion, comment,
             status, created, created, 2 if status == "confirmed" else None),
        )

    notifications = [
        (3, "Бронь подтверждена", "Ждём вас сегодня в 19:00, стол 3 в основном зале.", "/account/bookings", 0, 1),
        (3, "Добро пожаловать в ЧайHouse", "Сохраняйте любимые блюда и следите за бронями в личном кабинете.", "/account", 1, 2),
        (4, "Бронь подтверждена", "VIP-зал, через два дня в 19:00. Если нужен торт — просто ответьте на звонок администратора.", "/account/bookings", 0, 1),
    ]
    for user_id, title, body, link, is_read, days_ago in notifications:
        created = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
        db.execute(
            "INSERT INTO notifications(user_id, title, body, link, is_read, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, title, body, link, is_read, created),
        )

    dish_ids = {
        row["slug"]: row["id"] for row in db.execute("SELECT id, slug FROM dishes").fetchall()
    }
    for user_id, slug in [(3, "plov-chaihouse"), (3, "eggplant-salad"), (4, "shashlik-lamb")]:
        db.execute(
            "INSERT INTO favorites(user_id, dish_id, created_at) VALUES (?, ?, ?)",
            (user_id, dish_ids[slug], now),
        )

    audit_rows = [
        (1, "seed", "settings", "initial", json.dumps({"version": SCHEMA_VERSION}, ensure_ascii=False)),
        (2, "booking.confirmed", "booking", "CH-DEMO01", json.dumps({"source": "seed"}, ensure_ascii=False)),
    ]
    for actor_id, action, entity_type, entity_id, meta in audit_rows:
        db.execute(
            "INSERT INTO audit_log(actor_id, action, entity_type, entity_id, meta, ip, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (actor_id, action, entity_type, entity_id, meta, "127.0.0.1", now),
        )

    from core import DEFAULT_SETTINGS

    for key, value in DEFAULT_SETTINGS.items():
        db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (key, value))

    db.commit()
    return True


def register_cli(app) -> None:
    @app.cli.command("init-db")
    def init_db_command():
        """Создать схему и демо-данные."""
        init_db()
        click.echo("База данных инициализирована.")

    @app.cli.command("seed")
    def seed_command():
        """Заполнить пустую БД демо-данными."""
        created = seed_db(get_db())
        click.echo("Демо-данные добавлены." if created else "БД уже содержит данные.")

    @app.cli.command("check-db")
    def check_db_command():
        """Проверить целостность БД и внешние ключи."""
        db = get_db()
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        foreign = db.execute("PRAGMA foreign_key_check").fetchall()
        click.echo(f"integrity_check: {integrity}")
        click.echo(f"foreign_key_check: {'ok' if not foreign else foreign}")

    @app.cli.command("backup-db")
    def backup_db_command():
        """Создать резервную копию базы данных."""
        from services.backup import create_backup

        path, kept = create_backup()
        click.echo(f"Копия создана: {path.name} (всего копий: {kept})")

    @app.cli.command("send-reminders")
    def send_reminders_command():
        """Отправить напоминания о завтрашних бронях."""
        from services.notify import send_upcoming_reminders

        sent, skipped = send_upcoming_reminders()
        click.echo(f"Напоминаний отправлено: {sent}, пропущено (нет контакта): {skipped}")


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
    register_cli(app)
