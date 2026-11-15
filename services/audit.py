"""Журнал критичных действий."""

from __future__ import annotations

import json

from flask import g

from core import client_ip, utc_stamp
from database import get_db


def log_action(
    action: str,
    entity_type: str | None = None,
    entity_id: str | int | None = None,
    meta: dict | None = None,
    actor_id: int | None = None,
) -> None:
    if actor_id is None and g.get("user") is not None:
        actor_id = g.user["id"]
    payload = json.dumps(meta or {}, ensure_ascii=False)[:2000]
    get_db().execute(
        "INSERT INTO audit_log(actor_id, action, entity_type, entity_id, meta, ip, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            actor_id,
            action[:80],
            (entity_type or "")[:40] or None,
            str(entity_id)[:80] if entity_id is not None else None,
            payload,
            client_ip(),
            utc_stamp(),
        ),
    )
