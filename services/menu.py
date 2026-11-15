"""Меню, категории и избранное."""

from __future__ import annotations

import re

from core import SLUG_RE, utc_stamp
from database import get_db
from services.common import paginate

SORTS = {
    "popular": "(SELECT COUNT(*) FROM favorites f WHERE f.dish_id = d.id) DESC, d.is_signature DESC, d.sort_order, d.name",
    "price_asc": "d.price ASC, d.name",
    "price_desc": "d.price DESC, d.name",
    "name": "d.name COLLATE NOCASE",
    "new": "d.created_at DESC",
}
TAGS = {"vegetarian": "d.is_vegetarian = 1", "spicy": "d.is_spicy = 1", "signature": "d.is_signature = 1"}


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def list_categories() -> list:
    return (
        get_db()
        .execute(
            "SELECT c.*, (SELECT COUNT(*) FROM dishes d WHERE d.category_id = c.id AND d.is_active = 1) "
            "AS dish_count FROM menu_categories c ORDER BY c.sort_order, c.name"
        )
        .fetchall()
    )


def get_category(slug: str):
    return get_db().execute("SELECT * FROM menu_categories WHERE slug = ?", (slug,)).fetchone()


def list_dishes(
    q: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    sort: str = "popular",
    page: int | str | None = 1,
    per_page: int = 9,
    include_inactive: bool = False,
) -> tuple[list, dict, dict]:
    db = get_db()
    where: list[str] = []
    params: list = []
    if not include_inactive:
        where.append("d.is_active = 1")
    if q:
        term = q.strip()[:80]
        if term:
            where.append(
                "(py_lower(d.name) LIKE py_lower(?) ESCAPE '\\' "
                "OR py_lower(d.short_description) LIKE py_lower(?) ESCAPE '\\' "
                "OR py_lower(d.description) LIKE py_lower(?) ESCAPE '\\')"
            )
            params.extend([_like(term)] * 3)
    if category:
        where.append("c.slug = ?")
        params.append(category)
    if tag in TAGS:
        where.append(TAGS[tag])
    where_sql = " WHERE " + " AND ".join(where) if where else ""
    sort_sql = SORTS.get(sort, SORTS["popular"])

    count_row = db.execute(
        "SELECT COUNT(*) AS n FROM dishes d JOIN menu_categories c ON c.id = d.category_id" + where_sql,
        params,
    ).fetchone()
    total = count_row["n"]
    pagination = paginate(page, total, per_page)

    rows = db.execute(
        "SELECT d.*, c.name AS category_name, c.slug AS category_slug, "
        "(SELECT COUNT(*) FROM favorites f WHERE f.dish_id = d.id) AS favorites_count "
        "FROM dishes d JOIN menu_categories c ON c.id = d.category_id"
        + where_sql
        + f" ORDER BY {sort_sql} LIMIT ? OFFSET ?",
        params + [pagination["per_page"], pagination["offset"]],
    ).fetchall()
    filters = {
        "q": (q or "")[:80],
        "category": category or "",
        "tag": tag or "",
        "sort": sort if sort in SORTS else "popular",
    }
    return rows, pagination, filters


def get_dish(slug: str, include_inactive: bool = False):
    sql = (
        "SELECT d.*, c.name AS category_name, c.slug AS category_slug, "
        "(SELECT COUNT(*) FROM favorites f WHERE f.dish_id = d.id) AS favorites_count "
        "FROM dishes d JOIN menu_categories c ON c.id = d.category_id WHERE d.slug = ?"
    )
    if not include_inactive:
        sql += " AND d.is_active = 1"
    return get_db().execute(sql, (slug,)).fetchone()


def get_dish_by_id(dish_id: int):
    return (
        get_db()
        .execute(
            "SELECT d.*, c.name AS category_name FROM dishes d "
            "JOIN menu_categories c ON c.id = d.category_id WHERE d.id = ?",
            (dish_id,),
        )
        .fetchone()
    )


def related_dishes(dish, limit: int = 3) -> list:
    return (
        get_db()
        .execute(
            "SELECT d.*, c.name AS category_name FROM dishes d "
            "JOIN menu_categories c ON c.id = d.category_id "
            "WHERE d.is_active = 1 AND d.id != ? AND d.category_id = ? "
            "ORDER BY d.is_signature DESC, d.sort_order LIMIT ?",
            (dish["id"], dish["category_id"], limit),
        )
        .fetchall()
    )


def signature_dishes(limit: int = 4) -> list:
    return (
        get_db()
        .execute(
            "SELECT d.*, c.name AS category_name FROM dishes d "
            "JOIN menu_categories c ON c.id = d.category_id "
            "WHERE d.is_active = 1 AND d.is_signature = 1 "
            "ORDER BY d.sort_order, d.name LIMIT ?",
            (limit,),
        )
        .fetchall()
    )


def favorite_ids(user_id: int | None) -> set[int]:
    if not user_id:
        return set()
    rows = get_db().execute("SELECT dish_id FROM favorites WHERE user_id = ?", (user_id,)).fetchall()
    return {row["dish_id"] for row in rows}


def toggle_favorite(user_id: int, dish_id: int) -> tuple[bool, int]:
    db = get_db()
    dish = db.execute("SELECT id FROM dishes WHERE id = ? AND is_active = 1", (dish_id,)).fetchone()
    if not dish:
        raise ValueError("Блюдо не найдено.")
    exists = db.execute(
        "SELECT 1 FROM favorites WHERE user_id = ? AND dish_id = ?", (user_id, dish_id)
    ).fetchone()
    if exists:
        db.execute("DELETE FROM favorites WHERE user_id = ? AND dish_id = ?", (user_id, dish_id))
        active = False
    else:
        db.execute(
            "INSERT INTO favorites(user_id, dish_id, created_at) VALUES (?, ?, ?)",
            (user_id, dish_id, utc_stamp()),
        )
        active = True
    db.commit()
    count = db.execute("SELECT COUNT(*) AS n FROM favorites WHERE dish_id = ?", (dish_id,)).fetchone()["n"]
    return active, count


def favorites_for_user(user_id: int) -> list:
    return (
        get_db()
        .execute(
            "SELECT d.*, c.name AS category_name FROM favorites f "
            "JOIN dishes d ON d.id = f.dish_id JOIN menu_categories c ON c.id = d.category_id "
            "WHERE f.user_id = ? ORDER BY f.created_at DESC",
            (user_id,),
        )
        .fetchall()
    )


def _clean_dish_payload(form) -> tuple[dict, dict[str, str]]:
    db = get_db()
    errors: dict[str, str] = {}
    name = (form.get("name") or "").strip()
    slug = (form.get("slug") or "").strip().lower()
    if not slug and name:
        translit = {
            "а": "a",
            "б": "b",
            "в": "v",
            "г": "g",
            "д": "d",
            "е": "e",
            "ё": "e",
            "ж": "zh",
            "з": "z",
            "и": "i",
            "й": "y",
            "к": "k",
            "л": "l",
            "м": "m",
            "н": "n",
            "о": "o",
            "п": "p",
            "р": "r",
            "с": "s",
            "т": "t",
            "у": "u",
            "ф": "f",
            "х": "h",
            "ц": "c",
            "ч": "ch",
            "ш": "sh",
            "щ": "sch",
            "ъ": "",
            "ы": "y",
            "ь": "",
            "э": "e",
            "ю": "yu",
            "я": "ya",
        }
        slug = "".join(translit.get(ch, ch) for ch in name.lower())
        slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")[:70]
    if not (2 <= len(name) <= 120):
        errors["name"] = "Название должно быть от 2 до 120 символов."
    if not SLUG_RE.match(slug):
        errors["slug"] = "Короткий адрес: латиница, цифры и дефис, от 2 до 80 символов."
    category_id = form.get("category_id", type=int)
    if (
        not category_id
        or not db.execute("SELECT 1 FROM menu_categories WHERE id = ?", (category_id,)).fetchone()
    ):
        errors["category_id"] = "Выберите категорию."
    try:
        price = int(form.get("price", "0"))
    except (TypeError, ValueError):
        price = -1
    if not 0 <= price <= 100000:
        errors["price"] = "Цена должна быть числом от 0 до 100 000 ₽."
    short = (form.get("short_description") or "").strip()
    description = (form.get("description") or "").strip()
    if not (5 <= len(short) <= 180):
        errors["short_description"] = "Короткое описание — от 5 до 180 символов."
    if not (10 <= len(description) <= 3000):
        errors["description"] = "Описание — от 10 до 3000 символов."
    weight = (form.get("weight") or "").strip()[:40]
    allergens = (form.get("allergens") or "").strip()[:120]
    calories_raw = (form.get("calories") or "").strip()
    calories = None
    if calories_raw:
        try:
            calories = int(calories_raw)
            if not 0 <= calories <= 5000:
                raise ValueError
        except ValueError:
            errors["calories"] = "Калорийность — целое число от 0 до 5000."
    sort_order = form.get("sort_order", type=int) or 0
    payload = {
        "name": name,
        "slug": slug,
        "category_id": category_id,
        "price": price,
        "short_description": short,
        "description": description,
        "weight": weight,
        "allergens": allergens,
        "calories": calories,
        "is_vegetarian": 1 if form.get("is_vegetarian") else 0,
        "is_spicy": 1 if form.get("is_spicy") else 0,
        "is_signature": 1 if form.get("is_signature") else 0,
        "is_active": 1 if form.get("is_active") else 0,
        "sort_order": max(-999, min(999, sort_order)),
    }
    return payload, errors


def create_dish(form, image_path: str) -> tuple[int | None, dict[str, str]]:
    payload, errors = _clean_dish_payload(form)
    db = get_db()
    if db.execute("SELECT 1 FROM dishes WHERE slug = ?", (payload["slug"],)).fetchone():
        errors["slug"] = "Такой короткий адрес уже занят."
    if errors:
        return None, errors
    now = utc_stamp()
    cursor = db.execute(
        "INSERT INTO dishes(category_id, slug, name, short_description, description, price, weight, "
        "calories, allergens, image, is_vegetarian, is_spicy, is_signature, is_active, sort_order, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            payload["category_id"],
            payload["slug"],
            payload["name"],
            payload["short_description"],
            payload["description"],
            payload["price"],
            payload["weight"],
            payload["calories"],
            payload["allergens"],
            image_path,
            payload["is_vegetarian"],
            payload["is_spicy"],
            payload["is_signature"],
            payload["is_active"],
            payload["sort_order"],
            now,
            now,
        ),
    )
    db.commit()
    return cursor.lastrowid, {}


def update_dish(dish_id: int, form, image_path: str | None = None) -> dict[str, str]:
    payload, errors = _clean_dish_payload(form)
    db = get_db()
    if db.execute("SELECT 1 FROM dishes WHERE slug = ? AND id != ?", (payload["slug"], dish_id)).fetchone():
        errors["slug"] = "Такой короткий адрес уже занят."
    if errors:
        return errors
    existing = db.execute("SELECT image FROM dishes WHERE id = ?", (dish_id,)).fetchone()
    if not existing:
        return {"_": "Блюдо не найдено."}
    db.execute(
        "UPDATE dishes SET category_id = ?, slug = ?, name = ?, short_description = ?, description = ?, "
        "price = ?, weight = ?, calories = ?, allergens = ?, image = ?, is_vegetarian = ?, is_spicy = ?, "
        "is_signature = ?, is_active = ?, sort_order = ?, updated_at = ? WHERE id = ?",
        (
            payload["category_id"],
            payload["slug"],
            payload["name"],
            payload["short_description"],
            payload["description"],
            payload["price"],
            payload["weight"],
            payload["calories"],
            payload["allergens"],
            image_path or existing["image"],
            payload["is_vegetarian"],
            payload["is_spicy"],
            payload["is_signature"],
            payload["is_active"],
            payload["sort_order"],
            utc_stamp(),
            dish_id,
        ),
    )
    db.commit()
    return {}


def toggle_dish_active(dish_id: int) -> bool:
    db = get_db()
    row = db.execute("SELECT is_active FROM dishes WHERE id = ?", (dish_id,)).fetchone()
    if not row:
        raise ValueError("Блюдо не найдено.")
    new_value = 0 if row["is_active"] else 1
    db.execute(
        "UPDATE dishes SET is_active = ?, updated_at = ? WHERE id = ?", (new_value, utc_stamp(), dish_id)
    )
    db.commit()
    return bool(new_value)


def admin_dishes() -> list:
    return (
        get_db()
        .execute(
            "SELECT d.*, c.name AS category_name FROM dishes d "
            "JOIN menu_categories c ON c.id = d.category_id ORDER BY c.sort_order, d.sort_order, d.name"
        )
        .fetchall()
    )


def delete_dish(dish_id: int) -> None:
    db = get_db()
    db.execute("DELETE FROM dishes WHERE id = ?", (dish_id,))
    db.commit()
