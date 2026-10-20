from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import ORMModel


class MerchantRuleCreate(ORMModel):
    merchant_pattern: str = Field(min_length=1, max_length=160)
    category_id: int = Field(gt=0)
    confidence: Decimal = Field(default=Decimal("1"), ge=0, le=1, max_digits=5, decimal_places=4)


class MerchantRuleUpdate(ORMModel):
    merchant_pattern: str | None = Field(default=None, min_length=1, max_length=160)
    category_id: int | None = Field(default=None, gt=0)
    confidence: Decimal | None = Field(default=None, ge=0, le=1, max_digits=5, decimal_places=4)


class MerchantRuleResponse(ORMModel):
    id: int
    merchant_pattern: str
    category_id: int
    confidence: Decimal
    created_at: datetime
    updated_at: datetime