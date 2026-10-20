from datetime import date
from decimal import Decimal
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.planning import AffordabilityAnalyzeRequest, WhatIfRequest
from app.schemas.simulations import ContributionSimulationRequest, FixedDepositSimulationRequest


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None

    @field_validator("message")
    @classmethod
    def trim_message(cls, value):
        if not value.strip():
            raise ValueError("Enter a question")
        return value.strip()


class CoachAnswer(StrictModel):
    message: str = Field(min_length=1, max_length=6000)
    suggested_followups: list[str] = Field(max_length=3)
    warnings: list[str] = Field(max_length=5)
    needs_information: bool


class ChatResponse(StrictModel):
    provider: Literal["demo", "openai"] = "openai"
    message: str
    conversation_id: UUID
    tools_used: list[str] = Field(default_factory=list)
    suggested_followups: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EmptyArgs(StrictModel):
    pass


class GoalArgs(StrictModel):
    goal_id: int = Field(gt=0)


class CategoryArgs(StrictModel):
    category: str = Field(min_length=1, max_length=100)


class PurchaseArgs(AffordabilityAnalyzeRequest):
    model_config = ConfigDict(extra="forbid")
    # Explicitly excluded from model-accessible arguments; executor injects identity.
    user_id: None = Field(default=None, exclude=True)


class ScenarioArgs(WhatIfRequest):
    model_config = ConfigDict(extra="forbid")


class ContributionArgs(ContributionSimulationRequest):
    model_config = ConfigDict(extra="forbid")


class DepositArgs(FixedDepositSimulationRequest):
    model_config = ConfigDict(extra="forbid")


class GoalScenarioArgs(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    target_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    current_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    target_date: date


class PurchaseDelayArgs(StrictModel):
    delay_months: int = Field(ge=1, le=120)
