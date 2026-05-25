"""Pydantic field serializers.

All ``datetime`` values written by the app come from
``datetime.now(timezone.utc)``, but SQLite drops ``tzinfo`` on read so
SQLModel hands them back as naive datetimes. If we serialized them as-is
the JS side would parse them as local time and shift by the UTC offset
(eg. 19:00 CST showing as 11:00). Reattaching ``timezone.utc`` before
``isoformat()`` keeps the wire format unambiguous.
"""

from __future__ import annotations

from datetime import datetime, timezone


def serialize_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
