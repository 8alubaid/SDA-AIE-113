"""Wire contract - what a CLIENT sends/receives. Kept separate from
domain.entities.Transaction on purpose: this shape can change (API v2)
without touching what "a transaction" means internally, and vice versa."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from fraud_service.domain.entities import Channel, Decision, Transaction


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown fields = typo = reject loudly

    transaction_id: str = Field(min_length=8, max_length=64)
    amount_sar: float = Field(gt=0, le=1_000_000)
    channel: Channel
    merchant_category: str = Field(min_length=2, max_length=40)
    customer_id: str = Field(min_length=4, max_length=64)
    timestamp: datetime

    @field_validator("amount_sar", mode="before")
    @classmethod
    def reject_bool_amount(cls, v):
        # bool is a subclass of int in Python - JSON true/false would
        # otherwise silently coerce to 1.0/0.0 and pass the gt/le checks.
        if isinstance(v, bool):
            raise ValueError("amount_sar must be a number, not a boolean")  # noqa: TRY004
        return v

    @field_validator("merchant_category")
    @classmethod
    def reject_blank_mcc(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("merchant_category must not be blank")
        return v

    def to_domain(self) -> Transaction:
        return Transaction(**self.model_dump())


class PredictResponse(BaseModel):
    transaction_id: str
    fraud_probability: float = Field(ge=0, le=1)
    decision: Decision
    model_version: str
    trace_id: str


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
