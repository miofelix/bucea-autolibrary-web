from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.crypto import PasswordEncryptor
from app.core.errors import ConflictError, NotFoundError
from app.db.models import LibraryUser
from app.schemas.user import LibraryUserCreate, LibraryUserUpdate


class UserService:
    def __init__(self, session: Session):
        self._session = session
        self._encryptor = PasswordEncryptor.from_settings()

    def list_users(self) -> list[LibraryUser]:
        statement = select(LibraryUser).order_by(LibraryUser.id)
        return list(self._session.exec(statement).all())

    def get_user(self, user_id: int) -> LibraryUser:
        user = self._session.get(LibraryUser, user_id)
        if user is None:
            raise NotFoundError("library user not found")
        return user

    def create_user(self, payload: LibraryUserCreate) -> LibraryUser:
        user = LibraryUser(
            username=payload.username,
            display_name=payload.display_name,
            password_encrypted=self._encryptor.encrypt(payload.password),
            enabled=payload.enabled,
            notes=payload.notes,
        )
        self._session.add(user)
        self._commit_or_conflict()
        self._session.refresh(user)
        return user

    def update_user(self, user_id: int, payload: LibraryUserUpdate) -> LibraryUser:
        user = self.get_user(user_id)
        update_data = payload.model_dump(exclude_unset=True)
        password = update_data.pop("password", None)
        for key, value in update_data.items():
            setattr(user, key, value)
        if password is not None:
            user.password_encrypted = self._encryptor.encrypt(password)
        user.updated_at = datetime.now(timezone.utc)
        self._session.add(user)
        self._commit_or_conflict()
        self._session.refresh(user)
        return user

    def delete_user(self, user_id: int) -> None:
        user = self.get_user(user_id)
        self._session.delete(user)
        self._session.commit()

    def _commit_or_conflict(self) -> None:
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError("library username already exists") from exc
