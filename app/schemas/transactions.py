from __future__ import annotations

from datetime import date as DateType
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.models.enums import TransactionType
from app.schemas.base import ORMModel


class TransactionCreate(ORMModel):
    user_id: int | None = Field(default=None, gt=0)
    date: DateType
    description: str = Field(min_length=1, max_length=240)
    merchant: str = Field(min_length=1, max_length=160)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    transaction_type: TransactionType
    category_id: int | None = Field(default=None, gt=0)
    notes: str | None = None


class TransactionUpdate(ORMModel):
    date: DateType | None = None
    description: str | None = Field(default=None, min_length=1, max_length=240)
    merchant: str | None = Field(default=None, min_length=1, max_length=160)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    transaction_type: TransactionType | None = None
    category_id: int | None = Field(default=None, gt=0)
    notes: str | None = None


class TransactionResponse(ORMModel):
    id: int
    user_id: int
    date: DateType
    description: str
    merchant: str
    amount: Decimal
    transaction_type: TransactionType
    category_id: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class TransactionListResponse(ORMModel):
    items: list[TransactionResponse]
    total: int
    page: int
    page_size: int