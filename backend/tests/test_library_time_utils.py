import pytest

from app.library.time_utils import (
    label_to_minutes,
    minutes_to_label,
    normalize_time_value,
)


@pytest.mark.parametrize(
    "minute,label",
    [
        (0, "00:00"),
        (480, "08:00"),
        (960, "16:00"),
        (990, "16:30"),
        (1320, "22:00"),
        (1350, "22:30"),
    ],
)
def test_minutes_to_label_round_trip(minute: int, label: str) -> None:
    assert minutes_to_label(minute) == label
    assert label_to_minutes(label) == minute


def test_minutes_out_of_range_raises() -> None:
    with pytest.raises(ValueError):
        minutes_to_label(-1)
    with pytest.raises(ValueError):
        minutes_to_label(24 * 60)


def test_label_to_minutes_invalid() -> None:
    with pytest.raises(ValueError):
        label_to_minutes("1600")
    with pytest.raises(ValueError):
        label_to_minutes("24:00")


def test_normalize_time_value_preserves_now() -> None:
    assert normalize_time_value(" now ") == "now"
    assert normalize_time_value("960") == "960"


def test_normalize_time_value_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        normalize_time_value("-5")
    with pytest.raises(ValueError):
        normalize_time_value("99999")
