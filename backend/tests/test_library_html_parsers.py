import pytest

from app.library.errors import CaptchaRequiredError, LibraryParseError
from app.library.html_parsers import (
    parse_history,
    parse_page_context,
    parse_reservation_detail,
    parse_rooms,
    parse_search_response,
    parse_seats,
    parse_start_times,
    parse_time_options,
)


def test_parse_rooms_extracts_value_text_pairs() -> None:
    html = """
        <a href="#" value="1">二层内环区</a>
        <a href="#" value="2">二层西区</a>
        <a href="#">没有 value 不应入选</a>
        <a href="#" value="3"></a>
    """
    rooms = parse_rooms(html)
    assert [(r.room_id, r.name) for r in rooms] == [("1", "二层内环区"), ("2", "二层西区")]


def test_parse_seats_extracts_id_status_room() -> None:
    html = """
        <ul>
          <li class="free" id="seat_5775" title="座位空闲">
            <dl><dt>001A</dt><dd>二层内环区</dd></dl>
          </li>
          <li class="using" id="seat_5776" title="正在使用中">
            <dl><dt>001B</dt><dd>二层内环区</dd></dl>
          </li>
          <li class="legend">图例</li>
        </ul>
    """
    seats = parse_seats(html)
    assert len(seats) == 2
    assert seats[0].seat_id == 5775
    assert seats[0].name == "001A"
    assert seats[0].status == "free"
    assert seats[0].room_name == "二层内环区"
    assert seats[0].title == "座位空闲"
    assert seats[1].status == "using"


def test_parse_search_response_decodes_envelope() -> None:
    payload = {
        "seatStr": '<li class="free" id="seat_1"><dl><dt>001A</dt><dd>内环</dd></dl></li>',
        "seatNum": 1,
        "onDate": {"year": 2026, "monthOfYear": 5, "dayOfMonth": 25},
        "offset": 2,
    }
    result = parse_search_response(payload)
    assert result.seat_num == 1
    assert result.next_offset == 2
    assert result.on_date == "2026-05-25"
    assert result.seats[0].seat_id == 1


def test_parse_search_response_raises_on_rate_limit() -> None:
    with pytest.raises(CaptchaRequiredError):
        parse_search_response({"limit": True})


def test_parse_search_response_requires_dict() -> None:
    with pytest.raises(LibraryParseError):
        parse_search_response("not-json")  # type: ignore[arg-type]


def test_parse_time_options_extracts_now_and_minutes() -> None:
    html = """
        <li><a href="#" time="now">现在</a></li>
        <li><a href="#" time="960">16:00</a></li>
        <li><a href="#" time="990">16:30</a></li>
        <li><a href="#">no time</a></li>
    """
    options = parse_time_options(html)
    assert [(o.raw_value, o.label) for o in options] == [
        ("now", "现在"),
        ("960", "16:00"),
        ("990", "16:30"),
    ]


def test_parse_start_times_extracts_hidden_inputs() -> None:
    html = """
        <input type="hidden" name="seat" value="5775" id="seat" />
        <input type="hidden" name="room" value="二层内环区" id="room" />
        <input type="hidden" name="building" value="图书馆" id="building" />
        <li><a href="#" time="960">16:00</a></li>
    """
    result = parse_start_times(html)
    assert result.seat_id == 5775
    assert result.room_name == "二层内环区"
    assert result.building_name == "图书馆"
    assert len(result.options) == 1


def test_parse_page_context_extracts_csrf_and_user_info() -> None:
    html = """
        <input type="hidden" id="sysUsername" value="202404020113" />
        <input type="hidden" id="sysToken" value="abc" />
        <input type="hidden" name="SYNCHRONIZER_TOKEN" id="SYNCHRONIZER_TOKEN" value="tok" />
        <input type="hidden" name="SYNCHRONIZER_URI" id="SYNCHRONIZER_URI" value="/self" />
        <input type="hidden" name="authid" id="authid" value="-1" />
        <script>
          var userInfo = '{"currentReservationStatus":"NO_RESERVATION","userCheckedIn":false}';
        </script>
    """
    ctx = parse_page_context(html)
    assert ctx.sys_username == "202404020113"
    assert ctx.synchronizer_token == "tok"
    assert ctx.synchronizer_uri == "/self"
    assert ctx.authid == "-1"
    assert ctx.user_info == {
        "currentReservationStatus": "NO_RESERVATION",
        "userCheckedIn": False,
    }


def test_parse_history_decodes_dl_layout_from_legacy_client() -> None:
    """DOM layout mirrors the historical desktop client's reservation parser.

    Each reservation is a ``dl`` inside ``.myReserveList`` whose ``dt``
    carries ``"<date label> HH:MM -- HH:MM"`` and whose ``a`` children
    carry status keywords and the ``/view?id=...`` link.
    """
    html = """
        <div class="myReserveList">
          <dl>
            <dt>明天 16:00 -- 22:30</dt>
            <a href="/view?id=1230935&type=SEAT">已预约</a>
            <a href="javascript:void(0)">图书馆2层二层西区 001C</a>
          </dl>
          <dl>
            <dt>2026-05-20 07:30 -- 15:30</dt>
            <a href="/view?id=1228889&type=SEAT">已取消</a>
            <a href="javascript:void(0)">图书馆3层三层外环区 013A</a>
          </dl>
          <dl id="moreBlock"><dt>more</dt></dl>
        </div>
    """
    entries = parse_history(html)
    assert len(entries) == 2

    first = entries[0]
    assert first.reservation_id == "1230935"
    assert first.raw_date_label == "明天"
    assert first.start_label == "16:00"
    assert first.end_label == "22:30"
    assert first.status == "已预约"
    assert first.room_name == "图书馆2层二层西区 001C"

    second = entries[1]
    assert second.reservation_id == "1228889"
    assert second.date == "2026-05-20"
    assert second.status == "已取消"


def test_parse_reservation_detail_pulls_out_key_fields() -> None:
    html = """
        <html><body>
          <input type="hidden" id="reservationId" value="1230935" />
          凭证号 0113-935-2
          日期 2026-05-26 时间 07:30 -- 15:30
          位置 图书馆2层二层西区 座位 001C
          状态 已预约
        </body></html>
    """
    detail = parse_reservation_detail(html)
    assert detail.reservation_id == "1230935"
    assert detail.credential_no == "0113-935-2"
    assert detail.date == "2026-05-26"
    assert detail.start_label == "07:30"
    assert detail.end_label == "15:30"
    assert detail.seat_name == "001C"
    assert detail.status == "已预约"
    assert "图书馆" in (detail.room_name or "")

