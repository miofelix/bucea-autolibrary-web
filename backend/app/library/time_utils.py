from __future__ import annotations

from dataclasses import dataclass

OPENING_MINUTE = 0
CLOSING_MINUTE = 1380  # 23:00
SLOT_STEP_MINUTES = 30


@dataclass(frozen=True)
class TimeSlot:
    minute: int
    label: str


def minutes_to_label(minute: int) -> str:
    if minute < 0 or minute >= 24 * 60:
        raise ValueError(f"minute out of range: {minute}")
    hours, mins = divmod(minute, 60)
    return f"{hours:02d}:{mins:02d}"


def label_to_minutes(label: str) -> int:
    parts = label.split(":")
    if len(parts) != 2:
        raise ValueError(f"invalid HH:MM label: {label}")
    hours = int(parts[0])
    mins = int(parts[1])
    if not 0 <= hours < 24 or not 0 <= mins < 60:
        raise ValueError(f"invalid HH:MM label: {label}")
    return hours * 60 + mins


def normalize_time_value(raw: str) -> str:
    """Normalize a raw time attribute coming from the library system.

    The library returns minute counts as strings or the literal ``"now"``.
    Both forms are valid HTTP query values and must be preserved as-is.
    """
    text = raw.strip()
    if text == "now":
        return text
    minute = int(text)
    if minute < 0 or minute >= 24 * 60:
        raise ValueError(f"minute out of range: {minute}")
    return str(minute)
