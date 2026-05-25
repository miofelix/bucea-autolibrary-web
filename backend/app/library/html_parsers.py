"""HTML/JSON parsers for the library system responses.

Reference: docs/图书馆自动化工具开发辅助文档.md sections API-002 ~ API-013.
The library mostly returns HTML fragments via AJAX and a few JSON envelopes.
Everything in this module is pure: no HTTP, no IO, no side effects.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup

from app.library.errors import LibraryParseError


SEAT_ID_RE = re.compile(r"^seat\D*(\d+)$", re.IGNORECASE)


@dataclass(frozen=True)
class RoomOption:
    room_id: str
    name: str


@dataclass(frozen=True)
class SeatItem:
    seat_id: int
    name: str
    room_name: str | None
    status: str  # "free" | "using" | "booked" | "away" | "unavailable" | unknown class
    title: str | None


@dataclass(frozen=True)
class SearchResult:
    seats: tuple[SeatItem, ...]
    seat_num: int
    on_date: str | None
    next_offset: int


@dataclass(frozen=True)
class TimeOption:
    raw_value: str  # "now" or minute string
    label: str  # display text e.g. "16:00"


@dataclass(frozen=True)
class StartTimesResult:
    seat_id: int | None
    room_name: str | None
    building_name: str | None
    options: tuple[TimeOption, ...]


@dataclass(frozen=True)
class PageContext:
    sys_username: str | None
    sys_token: str | None
    synchronizer_token: str | None
    synchronizer_uri: str | None
    authid: str | None
    captcha_id: str | None
    user_info: dict[str, Any] | None


@dataclass(frozen=True)
class HistoryEntry:
    reservation_id: str | None
    credential_no: str | None
    seat_name: str | None
    room_name: str | None
    date: str | None
    start_label: str | None
    end_label: str | None
    status: str | None
    raw_date_label: str | None = None  # e.g. "明天"、"今天"、"2026-05-26"


@dataclass(frozen=True)
class ReservationDetail:
    reservation_id: str | None
    credential_no: str | None
    date: str | None
    start_label: str | None
    end_label: str | None
    seat_name: str | None
    room_name: str | None
    status: str | None
    raw_text: str


def _soup(html: str) -> BeautifulSoup:
    if not isinstance(html, str):
        raise LibraryParseError("expected str html input")
    return BeautifulSoup(html, "html.parser")


def parse_rooms(html: str) -> list[RoomOption]:
    soup = _soup(html)
    rooms: list[RoomOption] = []
    for tag in soup.find_all(["a", "li", "option"]):
        value = tag.get("value")
        text = tag.get_text(strip=True)
        if value is None or not text:
            continue
        rooms.append(RoomOption(room_id=str(value), name=text))
    return rooms


def _parse_seat_li(li) -> SeatItem | None:
    seat_id_attr = li.get("id", "")
    match = SEAT_ID_RE.match(seat_id_attr)
    if not match:
        return None
    seat_id = int(match.group(1))
    classes = li.get("class", []) or []
    status = classes[0] if classes else "unknown"
    dt = li.find("dt")
    dd = li.find("dd")
    name = dt.get_text(strip=True) if dt else ""
    room = dd.get_text(strip=True) if dd else None
    return SeatItem(
        seat_id=seat_id,
        name=name,
        room_name=room or None,
        status=status,
        title=li.get("title") or None,
    )


def parse_seats(html: str) -> list[SeatItem]:
    soup = _soup(html)
    seats: list[SeatItem] = []
    for li in soup.find_all("li"):
        item = _parse_seat_li(li)
        if item is not None:
            seats.append(item)
    return seats


def parse_search_response(payload: dict[str, Any]) -> SearchResult:
    if not isinstance(payload, dict):
        raise LibraryParseError("search response must be a JSON object")
    if payload.get("limit") is True:
        from app.library.errors import CaptchaRequiredError
        raise CaptchaRequiredError("rate limited by library; captcha required")
    seat_str = payload.get("seatStr") or ""
    seats = tuple(parse_seats(seat_str))
    seat_num_raw = payload.get("seatNum", len(seats))
    next_offset_raw = payload.get("offset", -1)
    on_date = _format_on_date(payload.get("onDate"))
    try:
        seat_num = int(seat_num_raw)
        next_offset = int(next_offset_raw)
    except (TypeError, ValueError) as exc:
        raise LibraryParseError("seatNum/offset must be integers") from exc
    return SearchResult(seats=seats, seat_num=seat_num, on_date=on_date, next_offset=next_offset)


def _format_on_date(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        year = value.get("year")
        month = value.get("monthOfYear") or value.get("month")
        day = value.get("dayOfMonth") or value.get("day")
        if year and month and day:
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return None


def parse_time_options(html: str) -> list[TimeOption]:
    soup = _soup(html)
    options: list[TimeOption] = []
    for anchor in soup.find_all("a"):
        raw = anchor.get("time")
        text = anchor.get_text(strip=True)
        if not raw:
            continue
        options.append(TimeOption(raw_value=str(raw), label=text or str(raw)))
    return options


def parse_start_times(html: str) -> StartTimesResult:
    soup = _soup(html)
    options = tuple(parse_time_options(html))
    seat_input = soup.find("input", attrs={"id": "seat"})
    room_input = soup.find("input", attrs={"id": "room"})
    building_input = soup.find("input", attrs={"id": "building"})
    seat_id_raw = seat_input.get("value") if seat_input else None
    seat_id = int(seat_id_raw) if seat_id_raw and str(seat_id_raw).isdigit() else None
    return StartTimesResult(
        seat_id=seat_id,
        room_name=room_input.get("value") if room_input else None,
        building_name=building_input.get("value") if building_input else None,
        options=options,
    )


def parse_page_context(html: str) -> PageContext:
    """Extract authentication and CSRF context from a fully rendered page.

    Used after every page navigation that returns the application's HTML
    shell. The library injects hidden inputs and a JavaScript ``userInfo``
    JSON blob into every authenticated page.
    """
    soup = _soup(html)

    def hidden(name: str) -> str | None:
        node = soup.find("input", attrs={"id": name})
        if node is None:
            node = soup.find("input", attrs={"name": name})
        if node is None:
            return None
        value = node.get("value")
        return str(value) if value is not None else None

    return PageContext(
        sys_username=hidden("sysUsername"),
        sys_token=hidden("sysToken"),
        synchronizer_token=hidden("SYNCHRONIZER_TOKEN"),
        synchronizer_uri=hidden("SYNCHRONIZER_URI"),
        authid=hidden("authid"),
        captcha_id=hidden("captchaId"),
        user_info=_extract_user_info(html),
    )


_USER_INFO_RE = re.compile(r"userInfo\s*=\s*'([^']*)'", re.DOTALL)


def _extract_user_info(html: str) -> dict[str, Any] | None:
    match = _USER_INFO_RE.search(html)
    if not match:
        return None
    raw = match.group(1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


RESERVATION_STATUS_KEYWORDS = (
    "已预约",
    "使用中",
    "已完成",
    "已结束使用",
    "已取消",
    "失约",
    "迟到",
    "暂离开",
    "已签到",
    "审核",
)


_TIME_RANGE_RE = re.compile(r"(\d{1,2}:\d{2})\s*-{1,2}\s*(\d{1,2}:\d{2})")
_DATE_RE = re.compile(r"(\d{4}-\d{1,2}-\d{1,2})")
_VIEW_HREF_RE = re.compile(r"/view\?id=(\d+)")


def parse_history(html: str) -> list[HistoryEntry]:
    """Parse ``/history?type=SEAT`` into reservation entries.

    Layout (per historical desktop client reservation parser):

    ``.myReserveList > dl`` (one per reservation, excluding ``#moreBlock``)
      ``dt`` text: ``"今天 16:00 -- 22:30"`` / ``"2026-05-26 07:30 -- 15:30"``
      ``a`` elements carry the status text (``已预约`` / ``使用中`` / ...)
        and the location (``"图书馆..."``)
      ``a[href*="/view?id="]`` exposes the reservation id.
    """
    soup = _soup(html)
    container = soup.find(class_="myReserveList") or soup
    entries: list[HistoryEntry] = []
    for dl in container.find_all("dl"):
        if dl.get("id") == "moreBlock":
            continue
        dt = dl.find("dt")
        if dt is None:
            continue
        dt_text = dt.get_text(" ", strip=True)
        if not dt_text:
            continue

        raw_date_label: str | None = None
        for token in ("今天", "明天", "昨天"):
            if token in dt_text:
                raw_date_label = token
                break

        date_match = _DATE_RE.search(dt_text)
        date_value = date_match.group(1) if date_match else raw_date_label

        time_match = _TIME_RANGE_RE.search(dt_text)
        start_label = time_match.group(1) if time_match else None
        end_label = time_match.group(2) if time_match else None

        status: str | None = None
        location: str | None = None
        reservation_id: str | None = None
        for anchor in dl.find_all("a"):
            text = anchor.get_text(strip=True)
            href = anchor.get("href", "") or ""
            id_match = _VIEW_HREF_RE.search(href)
            if id_match and not reservation_id:
                reservation_id = id_match.group(1)
            if not text:
                continue
            if status is None:
                for keyword in RESERVATION_STATUS_KEYWORDS:
                    if keyword in text:
                        status = keyword
                        break
            if location is None and "图书馆" in text:
                location = text

        entries.append(
            HistoryEntry(
                reservation_id=reservation_id,
                credential_no=None,
                seat_name=None,
                room_name=location,
                date=date_value,
                start_label=start_label,
                end_label=end_label,
                status=status,
                raw_date_label=raw_date_label,
            )
        )
    return entries


_CREDENTIAL_RE = re.compile(r"(\d{3,5}-\d{2,5}-\d{1,4})")


def parse_reservation_detail(html: str) -> ReservationDetail:
    """Parse ``/view?id=...&type=SEAT`` (per doc API-014).

    The page is server-rendered; the helper doc describes it as
    "显示凭证号、日期、时间、位置、状态". This parser walks the document
    text, pattern-matches the obvious fields and keeps the raw text as a
    fallback for fields the UI may want to render verbatim.
    """
    soup = _soup(html)
    text = soup.get_text(" ", strip=True)

    credential_match = _CREDENTIAL_RE.search(text)
    date_match = _DATE_RE.search(text)
    time_match = _TIME_RANGE_RE.search(text)

    status: str | None = None
    for keyword in RESERVATION_STATUS_KEYWORDS:
        if keyword in text:
            status = keyword
            break

    location_match = re.search(r"(图书馆[^\s]+)", text)
    seat_match = re.search(r"(\d{3}[A-Za-z])", text)

    reservation_id: str | None = None
    for input_tag in soup.find_all("input"):
        name = input_tag.get("name") or input_tag.get("id") or ""
        if name in {"id", "reservationId", "resId"}:
            value = input_tag.get("value")
            if value:
                reservation_id = str(value)
                break

    return ReservationDetail(
        reservation_id=reservation_id,
        credential_no=credential_match.group(1) if credential_match else None,
        date=date_match.group(1) if date_match else None,
        start_label=time_match.group(1) if time_match else None,
        end_label=time_match.group(2) if time_match else None,
        seat_name=seat_match.group(1) if seat_match else None,
        room_name=location_match.group(1) if location_match else None,
        status=status,
        raw_text=text,
    )

