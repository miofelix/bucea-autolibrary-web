from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CaptchaResponse(BaseModel):
    image_base64: str
    content_type: str
    captcha_id: str | None = None
    suggested_answer: str | None = None
    ocr_engine: str | None = None


class LoginResponse(BaseModel):
    success: bool
    message: str
    captcha_required: bool = False


class SessionStatusResponse(BaseModel):
    library_user_id: int
    logged_in: bool
    sys_username: str | None
    user_info: dict[str, Any] | None
    has_csrf: bool


class RoomResponse(BaseModel):
    room_id: str
    name: str


class SeatItemResponse(BaseModel):
    seat_id: int
    name: str
    room_name: str | None
    status: str
    title: str | None


class SearchResultResponse(BaseModel):
    seats: list[SeatItemResponse]
    seat_num: int
    on_date: str | None
    next_offset: int


class SeatSearchQuery(BaseModel):
    on_date: str | None = None
    building: str | None = None
    room: str | None = None
    hour: str | None = None
    start_min: str | None = None
    end_min: str | None = None
    power: str | None = None
    window: str | None = None
    offset: int = 1


class TimeOptionResponse(BaseModel):
    raw_value: str
    label: str


class StartTimesResponse(BaseModel):
    seat_id: int | None
    room_name: str | None
    building_name: str | None
    options: list[TimeOptionResponse]


class ReservationRequestBody(BaseModel):
    seat_id: int = Field(gt=0)
    start: str = Field(min_length=1, max_length=8)
    end: str = Field(min_length=1, max_length=8)
    date: str = Field(default="", max_length=10)


class MutationResponse(BaseModel):
    success: bool
    message: str
    raw: Any | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class HistoryEntryResponse(BaseModel):
    reservation_id: str | None
    credential_no: str | None
    seat_name: str | None
    room_name: str | None
    date: str | None
    start_label: str | None
    end_label: str | None
    status: str | None
    raw_date_label: str | None = None


class AnnouncementResponse(BaseModel):
    roll_text: str | None


class ReservationDetailResponse(BaseModel):
    reservation_id: str | None
    credential_no: str | None
    date: str | None
    start_label: str | None
    end_label: str | None
    seat_name: str | None
    room_name: str | None
    status: str | None
    raw_text: str
