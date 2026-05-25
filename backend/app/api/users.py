from fastapi import APIRouter, Depends, Response, status
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.user import LibraryUserCreate, LibraryUserRead, LibraryUserUpdate
from app.services.user_service import UserService

router = APIRouter()


def get_user_service(session: Session = Depends(get_session)) -> UserService:
    return UserService(session)


@router.get("", response_model=list[LibraryUserRead])
def list_users(service: UserService = Depends(get_user_service)):
    return service.list_users()


@router.post("", response_model=LibraryUserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: LibraryUserCreate,
    service: UserService = Depends(get_user_service),
):
    return service.create_user(payload)


@router.get("/{user_id}", response_model=LibraryUserRead)
def get_user(user_id: int, service: UserService = Depends(get_user_service)):
    return service.get_user(user_id)


@router.put("/{user_id}", response_model=LibraryUserRead)
def update_user(
    user_id: int,
    payload: LibraryUserUpdate,
    service: UserService = Depends(get_user_service),
):
    return service.update_user(user_id, payload)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, service: UserService = Depends(get_user_service)):
    service.delete_user(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
