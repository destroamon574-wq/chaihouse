"""Публичная часть сайта."""

from __future__ import annotations

import re
from datetime import date

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from core import (
    client_ip,
    get_settings,
    login_required,
    rate_limit,
    utc_stamp,
)
from database import get_db
from services.content import (
    GALLERY_CATEGORIES,
    create_review,
    get_gallery,
    get_hall,
    get_halls,
    hall_reviews,
    list_reviews,
    review_summary,
    top_reviews,
)
from services.menu import (
    favorite_ids,
    get_dish,
    list_categories,
    list_dishes,
    related_dishes,
    signature_dishes,
)
from services.uploads import image_url

bp = Blueprint("public", __name__)


def _canonical(path: str) -> str:
    return current_app.config["SITE_URL"].rstrip("/") + path


def _meta(title: str, description: str, path: str, image: str = "img/og-cover.jpg") -> dict:
    return {
        "page_title": title,
        "meta_description": description,
        "canonical": _canonical(path),
        "og_image": current_app.config["SITE_URL"].rstrip("/") + image_url(image),
    }


@bp.get("/")
def home():
    halls = get_halls()
    dishes = signature_dishes(4)
    reviews = top_reviews(3) or list_reviews("published", 1, 3)[0]
    gallery = get_gallery()
    summary = review_summary()
    schema = {
        "@context": "https://schema.org",
        "@type": "Restaurant",
        "name": get_settings()["restaurant_name"],
        "description": "Чайхана с восточной кухней на Ходынском бульваре в Москве.",
        "image": current_app.config["SITE_URL"].rstrip("/") + image_url("img/og-cover.jpg"),
        "url": current_app.config["SITE_URL"].rstrip("/") + "/",
        "telephone": get_settings()["phone"],
        "priceRange": "₽₽",
        "servesCuisine": ["Узбекская кухня", "Восточная кухня"],
        "address": {
            "@type": "PostalAddress",
            "streetAddress": get_settings()["address"],
            "addressLocality": "Москва",
            "addressCountry": "RU",
        },
        "geo": {
            "@type": "GeoCoordinates",
            "latitude": get_settings()["lat"],
            "longitude": get_settings()["lng"],
        },
        "openingHoursSpecification": {
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
            "opens": "12:00",
            "closes": "00:00",
        },
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": summary["avg"],
            "reviewCount": summary["count"],
        },
    }
    return render_template(
        "public/home.html",
        halls=halls,
        dishes=dishes,
        reviews=reviews,
        review_summary=summary,
        gallery=gallery[:6],
        favorites=favorite_ids(g.user["id"] if g.get("user") else None),
        schema=schema,
        **_meta(
            "ЧайHouse — чайхана с восточной кухней в Москве",
            "Плов, лагман, манты, шашлыки и чай в тёплом зале на Ходынском бульваре. "
            "Забронируйте стол или зал онлайн — подтвердим бронь в течение 15 минут.",
            "/",
        ),
    )


@bp.get("/menu")
def menu():
    categories = list_categories()
    dishes, pages, filters = list_dishes(
        q=request.args.get("q"),
        category=request.args.get("category"),
        tag=request.args.get("tag"),
        sort=request.args.get("sort", "popular"),
        page=request.args.get("page", 1),
        per_page=9,
    )
    canonical_path = "/menu"
    if filters["category"]:
        canonical_path += f"?category={filters['category']}"
    title = "Меню"
    if filters["category"]:
        category = next((c for c in categories if c["slug"] == filters["category"]), None)
        if category:
            title = f"Меню · {category['name']}"
    return render_template(
        "public/menu.html",
        categories=categories,
        dishes=dishes,
        pages=pages,
        filters=filters,
        favorites=favorite_ids(g.user["id"] if g.get("user") else None),
        **_meta(
            f"{title} — ЧайHouse",
            "Меню чайханы ЧайHouse: плов из казана, лагман, манты, шашлыки, кебабы, "
            "салаты из жареных баклажанов, самса и восточные чаи.",
            canonical_path,
        ),
    )


@bp.get("/menu/<slug>")
def dish(slug: str):
    item = get_dish(slug)
    if not item:
        abort(404)
    related = related_dishes(item)
    favorites = favorite_ids(g.user["id"] if g.get("user") else None)
    return render_template(
        "public/dish.html",
        dish=item,
        related=related,
        favorites=favorites,
        **_meta(
            f"{item['name']} — меню ЧайHouse",
            item["short_description"],
            f"/menu/{item['slug']}",
            item["image"] if item["image"].startswith("uploads/") else item["image"],
        ),
    )


@bp.get("/halls")
def halls():
    items = get_halls()
    return render_template(
        "public/halls.html",
        halls=items,
        **_meta(
            "Залы и банкеты — ЧайHouse",
            "Четыре зала ЧайHouse: основной зал, веранда, VIP-комната и банкетный зал "
            "до 40 гостей. Выберите зал и забронируйте стол онлайн.",
            "/halls",
        ),
    )


@bp.get("/halls/<slug>")
def hall(slug: str):
    item = get_hall(slug)
    if not item:
        abort(404)
    return render_template(
        "public/hall.html",
        hall=item,
        hall_reviews=hall_reviews(item["id"]),
        review_summary=review_summary(),
        **_meta(
            f"{item['name']} — залы ЧайHouse",
            item["tagline"] or item["description"][:150],
            f"/halls/{item['slug']}",
            item["image"],
        ),
    )


@bp.get("/gallery")
def gallery():
    category = request.args.get("category")
    if category not in GALLERY_CATEGORIES:
        category = None
    items = get_gallery(category)
    return render_template(
        "public/gallery.html",
        gallery=items,
        categories=GALLERY_CATEGORIES,
        active_category=category,
        **_meta(
            "Галерея — ЧайHouse",
            "Интерьер чайханы ЧайHouse: тёплый свет, резные узоры, бирюзовые диваны, "
            "VIP-зал и блюда восточной кухни.",
            "/gallery",
        ),
    )


@bp.get("/about")
def about():
    reviews, _ = list_reviews("published", 1, 3)
    return render_template(
        "public/about.html",
        reviews=reviews,
        review_summary=review_summary(),
        **_meta(
            "О чайхане — ЧайHouse",
            "ЧайHouse — место, где восточная кухня встречается с московским вечером. "
            "Готовим плов в казане, тянем лапшу, печём самсу и завариваем чай.",
            "/about",
        ),
    )


@bp.get("/contacts")
def contacts():
    return render_template(
        "public/contacts.html",
        **_meta(
            "Контакты и как добраться — ЧайHouse",
            "ЧайHouse: Москва, Ходынский бульвар, 4, ТРЦ «Авиапарк», 3 этаж. "
            "Ежедневно с 12:00 до 00:00. Телефон +7 (495) 120-48-18.",
            "/contacts",
        ),
    )


@bp.get("/reviews")
def reviews_page():
    reviews, pages = list_reviews("published", request.args.get("page", 1), 6)
    return render_template(
        "public/reviews.html",
        reviews=reviews,
        pages=pages,
        summary=review_summary(),
        **_meta(
            "Отзывы гостей — ЧайHouse",
            "Что гости говорят о плове, залах и сервисе ЧайHouse. Средняя оценка и живые отзывы.",
            "/reviews",
        ),
    )


@bp.post("/reviews")
@login_required
def create_review_route():
    allowed, retry = rate_limit(f"review:{client_ip()}", 5, 3600)
    if not allowed:
        flash("Слишком много отзывов за короткое время. Попробуйте позже.", "danger")
        return redirect(url_for("public.reviews_page"))
    ok, errors = create_review(g.user, request.form)
    if not ok:
        for message in errors.values():
            flash(message, "danger")
        return redirect(url_for("public.reviews_page") + "#review-form")
    flash("Спасибо! Отзыв отправлен на проверку — опубликуем после модерации.", "success")
    return redirect(url_for("public.reviews_page"))


@bp.get("/privacy")
def privacy():
    return render_template(
        "public/privacy.html",
        **_meta(
            "Политика конфиденциальности — ЧайHouse",
            "Как ЧайHouse обрабатывает персональные данные гостей и посетителей сайта.",
            "/privacy",
        ),
    )


@bp.get("/terms")
def terms():
    return render_template(
        "public/terms.html",
        **_meta(
            "Правила бронирования — ЧайHouse",
            "Правила бронирования столов и залов в чайхане ЧайHouse.",
            "/terms",
        ),
    )


@bp.get("/media/<path:filename>")
def media(filename: str):
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", filename):
        abort(404)
    directory = current_app.config["UPLOAD_DIR"]
    response = send_from_directory(directory, filename, max_age=31536000)
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


@bp.get("/robots.txt")
def robots():
    content = (
        "User-agent: *\n"
        "Disallow: /admin\n"
        "Disallow: /owner\n"
        "Disallow: /account\n"
        "Disallow: /auth\n"
        "Disallow: /booking\n"
        "Disallow: /api\n"
        "Sitemap: " + current_app.config["SITE_URL"].rstrip("/") + "/sitemap.xml\n"
    )
    return Response(content, mimetype="text/plain")


@bp.get("/sitemap.xml")
def sitemap():
    db = get_db()
    urls = [
        ("/", "1.0"),
        ("/menu", "0.9"),
        ("/halls", "0.9"),
        ("/gallery", "0.7"),
        ("/about", "0.7"),
        ("/contacts", "0.8"),
        ("/reviews", "0.6"),
        ("/privacy", "0.2"),
        ("/terms", "0.2"),
    ]
    for row in db.execute("SELECT slug FROM halls WHERE is_active = 1").fetchall():
        urls.append((f"/halls/{row['slug']}", "0.7"))
    for row in db.execute("SELECT slug FROM dishes WHERE is_active = 1").fetchall():
        urls.append((f"/menu/{row['slug']}", "0.6"))
    today = date.today().isoformat()
    body = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    base = current_app.config["SITE_URL"].rstrip("/")
    for path, priority in urls:
        body.append(
            f"<url><loc>{base}{path}</loc><lastmod>{today}</lastmod><priority>{priority}</priority></url>"
        )
    body.append("</urlset>")
    return Response("\n".join(body), mimetype="application/xml")


@bp.get("/healthz")
def healthz():
    db = get_db()
    db.execute("SELECT 1").fetchone()
    return {"ok": True, "time": utc_stamp()}
