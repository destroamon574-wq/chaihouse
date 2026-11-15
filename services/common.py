"""Общие сервисные помощники."""
from __future__ import annotations

import math


def paginate(page: int | str | None, total: int, per_page: int = 9) -> dict:
    try:
        current = int(page or 1)
    except (TypeError, ValueError):
        current = 1
    per_page = max(1, int(per_page))
    pages = max(1, math.ceil(total / per_page))
    current = min(max(1, current), pages)
    start = (current - 1) * per_page
    numbers = list(range(max(1, current - 2), min(pages, current + 2) + 1))
    return {
        "page": current,
        "pages": pages,
        "per_page": per_page,
        "total": total,
        "offset": start,
        "has_prev": current > 1,
        "has_next": current < pages,
        "prev": current - 1,
        "next": current + 1,
        "numbers": numbers,
        "first": start + 1 if total else 0,
        "last": min(total, start + per_page),
    }
