from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.core.serializers import serialize_utc


class LibraryUserBase(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    display_name: str | None = Field(default=None, max_length=128)
    enabled: bool = True
    notes: str | None = Field(default=None, max_length=512)


class LibraryUserCreate(LibraryUserBase):
    password: str = Field(min_length=1, max_length=256)


class LibraryUserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=128)
    display_name: str | None = Field(default=None, max_length=128)
    password: str | None = Field(default=None, min_length=1, max_length=256)
    enabled: bool | None = None
    notes: str | None = Field(default=None, max_length=512)


class LibraryUserRead(LibraryUserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "updated_at")
    def _ser_dt(self, value: datetime | None) -> str | None:
        return serialize_utc(value)
