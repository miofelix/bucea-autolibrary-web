from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from app.db.session import get_session
from app.library.client import SeatSearchFilters
from app.schemas.library import (
    AnnouncementResponse,
    CaptchaResponse,
    HistoryEntryResponse,
    LoginResponse,
    MutationResponse,
    ReservationDetailResponse,
    ReservationRequestBody,
    RoomResponse,
    SearchResultResponse,
    SeatItemResponse,
    SessionStatusResponse,
    StartTimesResponse,
    TimeOptionResponse,
)
from app.services.library_service import LibraryService

router = APIRouter()


def get_library_service(db_session: Session = Depends(get_session)) -> LibraryService:
    return LibraryService(db_session)


@router.post("/{library_user_id}/bootstrap")
async def bootstrap(
    library_user_id: int,
    service: LibraryService = Depends(get_library_service),
) -> dict[str, str | None]:
    return await service.bootstrap(library_user_id)


@router.get("/{library_user_id}/captcha", response_model=CaptchaResponse)
async def captcha(
    library_user_id: int,
    service: LibraryService = Depends(get_library_service),
) -> CaptchaResponse:
    image = await service.get_captcha(library_user_id)
    return CaptchaResponse(
        image_base64=image.image_base64,
        content_type=image.content_type,
        captcha_id=image.captcha_id,
        suggested_answer=image.suggested_answer,
        ocr_engine=image.ocr_engine,
    )


@router.post("/{library_user_id}/login", response_model=LoginResponse)
async def login(
    library_user_id: int,
    service: LibraryService = Depends(get_library_service),
) -> LoginResponse:
    outcome = await service.login(library_user_id)
    return LoginResponse(
        success=outcome.success,
        message=outcome.message,
        captcha_required=outcome.captcha_required,
    )


@router.post("/{library_user_id}/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    library_user_id: int,
    service: LibraryService = Depends(get_library_service),
) -> None:
    await service.logout(library_user_id)


@router.get("/{library_user_id}/session", response_model=SessionStatusResponse)
async def session_status(
    library_user_id: int,
    service: LibraryService = Depends(get_library_service),
) -> SessionStatusResponse:
    data = await service.session_status(library_user_id)
    return SessionStatusResponse(**data)


@router.get("/{library_user_id}/rooms", response_model=list[RoomResponse])
async def list_rooms(
    library_user_id: int,
    building: str = Query("1", min_length=1, max_length=8),
    service: LibraryService = Depends(get_library_service),
) -> list[RoomResponse]:
    rooms = await service.get_rooms(library_user_id, building)
    return [RoomResponse(room_id=r.room_id, name=r.name) for r in rooms]


@router.get("/{library_user_id}/seats", response_model=SearchResultResponse)
async def search_seats(
    library_user_id: int,
    service: LibraryService = Depends(get_library_service),
    on_date: str | None = Query(None),
    building: str | None = Query(None),
    room: str | None = Query(None),
    hour: str | None = Query(None),
    start_min: str | None = Query(None),
    end_min: str | None = Query(None),
    power: str | None = Query(None),
    window: str | None = Query(None),
    offset: int = Query(1, ge=1),
) -> SearchResultResponse:
    result = await service.search_seats(
        library_user_id,
        SeatSearchFilters(
            on_date=on_date,
            building=building,
            room=room,
            hour=hour,
            start_min=start_min,
            end_min=end_min,
            power=power,
            window=window,
            offset=offset,
        ),
    )
    return SearchResultResponse(
        seats=[
            SeatItemResponse(
                seat_id=s.seat_id,
                name=s.name,
                room_name=s.room_name,
                status=s.status,
                title=s.title,
            )
            for s in result.seats
        ],
        seat_num=result.seat_num,
        on_date=result.on_date,
        next_offset=result.next_offset,
    )


@router.get("/{library_user_id}/seats/{seat_id}/start-times", response_model=StartTimesResponse)
async def start_times(
    library_user_id: int,
    seat_id: int,
    date: str = Query(""),
    service: LibraryService = Depends(get_library_service),
) -> StartTimesResponse:
    result = await service.get_start_times(library_user_id, seat_id, date=date)
    return StartTimesResponse(
        seat_id=result.seat_id,
        room_name=result.room_name,
        building_name=result.building_name,
        options=[TimeOptionResponse(raw_value=o.raw_value, label=o.label) for o in result.options],
    )


@router.get("/{library_user_id}/seats/{seat_id}/end-times", response_model=list[TimeOptionResponse])
async def end_times(
    library_user_id: int,
    seat_id: int,
    start: str = Query(..., min_length=1, max_length=8),
    date: str = Query(""),
    service: LibraryService = Depends(get_library_service),
) -> list[TimeOptionResponse]:
    options = await service.get_end_times(
        library_user_id, start=start, seat_id=seat_id, date=date
    )
    return [TimeOptionResponse(raw_value=o.raw_value, label=o.label) for o in options]


@router.post("/{library_user_id}/reservations", response_model=MutationResponse)
async def submit_reservation(
    library_user_id: int,
    payload: ReservationRequestBody,
    service: LibraryService = Depends(get_library_service),
) -> MutationResponse:
    result = await service.submit_reservation(
        library_user_id,
        seat_id=payload.seat_id,
        start=payload.start,
        end=payload.end,
        date=payload.date,
    )
    return MutationResponse(success=result.success, message=result.message, raw=result.raw)


@router.post("/{library_user_id}/reservations/{reservation_id}/cancel", response_model=MutationResponse)
async def cancel_reservation(
    library_user_id: int,
    reservation_id: str,
    service: LibraryService = Depends(get_library_service),
) -> MutationResponse:
    result = await service.cancel_reservation(library_user_id, reservation_id)
    return MutationResponse(success=result.success, message=result.message, raw=result.raw)


@router.post("/{library_user_id}/check-in", response_model=MutationResponse)
async def check_in(
    library_user_id: int,
    service: LibraryService = Depends(get_library_service),
) -> MutationResponse:
    result = await service.check_in(library_user_id)
    return MutationResponse(success=result.success, message=result.message, raw=result.raw)


@router.post("/{library_user_id}/renew", response_model=MutationResponse)
async def renew(
    library_user_id: int,
    service: LibraryService = Depends(get_library_service),
) -> MutationResponse:
    result = await service.renew(library_user_id)
    return MutationResponse(success=result.success, message=result.message, raw=result.raw)


@router.post("/{library_user_id}/stop-using", response_model=MutationResponse)
async def stop_using(
    library_user_id: int,
    service: LibraryService = Depends(get_library_service),
) -> MutationResponse:
    result = await service.stop_using(library_user_id)
    return MutationResponse(success=result.success, message=result.message, raw=result.raw)


@router.post("/{library_user_id}/leave", response_model=MutationResponse)
async def leave(
    library_user_id: int,
    service: LibraryService = Depends(get_library_service),
) -> MutationResponse:
    result = await service.leave(library_user_id)
    return MutationResponse(success=result.success, message=result.message, raw=result.raw)


@router.post("/{library_user_id}/resume", response_model=MutationResponse)
async def resume(
    library_user_id: int,
    service: LibraryService = Depends(get_library_service),
) -> MutationResponse:
    result = await service.resume(library_user_id)
    return MutationResponse(success=result.success, message=result.message, raw=result.raw)


@router.get(
    "/{library_user_id}/reservations/{reservation_id}",
    response_model=ReservationDetailResponse,
)
async def reservation_detail(
    library_user_id: int,
    reservation_id: str,
    service: LibraryService = Depends(get_library_service),
) -> ReservationDetailResponse:
    detail = await service.get_reservation_detail(library_user_id, reservation_id)
    return ReservationDetailResponse(
        reservation_id=detail.reservation_id or reservation_id,
        credential_no=detail.credential_no,
        date=detail.date,
        start_label=detail.start_label,
        end_label=detail.end_label,
        seat_name=detail.seat_name,
        room_name=detail.room_name,
        status=detail.status,
        raw_text=detail.raw_text,
    )


@router.get("/{library_user_id}/reservations", response_model=list[HistoryEntryResponse])
async def list_reservations(
    library_user_id: int,
    service: LibraryService = Depends(get_library_service),
) -> list[HistoryEntryResponse]:
    history = await service.get_history(library_user_id)
    return [
        HistoryEntryResponse(
            reservation_id=h.reservation_id,
            credential_no=h.credential_no,
            seat_name=h.seat_name,
            room_name=h.room_name,
            date=h.date,
            start_label=h.start_label,
            end_label=h.end_label,
            status=h.status,
            raw_date_label=h.raw_date_label,
        )
        for h in history
    ]


@router.get("/{library_user_id}/announcement", response_model=AnnouncementResponse)
async def get_announcement(
    library_user_id: int,
    service: LibraryService = Depends(get_library_service),
) -> AnnouncementResponse:
    text = await service.get_roll_text(library_user_id)
    return AnnouncementResponse(roll_text=text)
