from pydantic import EmailStr, Field

from app.schemas.base import ORMModel


class UserCreate(ORMModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    age: int | None = Field(default=None, ge=18, le=100)


class UserResponse(UserCreate):
    id: int


class UserUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    age: int | None = Field(default=None, ge=18, le=100)