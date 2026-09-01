<<<<<<< HEAD
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
            raise TypeError("amount_sar must be a number, not a boolean")
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
=======
"""Wire contract for the prediction API.

This module is the wall between hostile JSON and the domain. Anything that
gets past it is guaranteed well-formed, so no layer behind it needs to
re-check: `domain/` deliberately contains no validation.
"""
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from fraud_service.domain.entities import Decision, Transaction

Channel = Literal["atm", "ecom", "pos", "transfer"]

# Identifiers are opaque strings, but never blank, spaced or emoji-laden.
ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
# Merchant categories may contain spaces; the domain normalises them later.
MCC_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9 _&-]*$"

MAX_AMOUNT_SAR = 1_000_000.0


def _parse_iso8601(value: object) -> object:
    """Accept ISO 8601 strings only.

    Pydantic would otherwise read an int - or a numeric *string* - as a Unix
    timestamp, so `1751753640000` would silently become a date instead of
    being rejected. Timestamps are normalised to UTC because `hour_of_day`
    is a model feature: an unpinned timezone is training/serving skew.
    """
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                "must be an ISO 8601 timestamp, e.g. 2026-07-05T22:14:00Z"
            ) from exc
    else:
        # Deliberately ValueError, not TypeError (ruff TRY004): pydantic
        # converts ValueError into a 422, but lets TypeError escape as a 500.
        raise ValueError(  # noqa: TRY004
            "must be an ISO 8601 timestamp string"
        )

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


Timestamp = Annotated[datetime, BeforeValidator(_parse_iso8601)]


def _reject_bool(value: object) -> object:
    """Reject booleans for numeric fields.

    `bool` subclasses `int` in Python, so pydantic's lax mode would coerce
    `true` to 1.0 - scoring a transaction against a fabricated 1 SAR amount
    and returning 200. Numbers must be numbers.
    """
    if isinstance(value, bool):
        raise ValueError("must be a number, not a boolean")  # noqa: TRY004
    return value


Amount = Annotated[float, BeforeValidator(_reject_bool)]


class PredictRequest(BaseModel):
    """One transaction to score.

    `extra="forbid"` is load-bearing: a client that misspells `amount_sar`
    as `amount_sr` must get a loud 422, not a silent score computed from a
    default.
    """

    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(
        min_length=8, max_length=64, pattern=ID_PATTERN
    )
    customer_id: str = Field(
        min_length=4, max_length=64, pattern=ID_PATTERN
    )
    amount_sar: Amount = Field(
        gt=0, le=MAX_AMOUNT_SAR, allow_inf_nan=False
    )
    channel: Channel
    merchant_category: str = Field(
        min_length=2, max_length=64, pattern=MCC_PATTERN
    )
    timestamp: Timestamp

    def to_domain(self) -> Transaction:
        """Cross the boundary into the domain.

        `customer_id` is part of the wire contract but not a model feature,
        so it deliberately does not appear on `Transaction`.
        """
        return Transaction(
            transaction_id=self.transaction_id,
            amount_sar=self.amount_sar,
            channel=self.channel,
            merchant_category=self.merchant_category,
            timestamp=self.timestamp,
        )


class PredictResponse(BaseModel):
    # Pydantic reserves the `model_` prefix; without this, `model_version`
    # emits a protected-namespace warning.
    model_config = ConfigDict(protected_namespaces=())

    transaction_id: str
    fraud_probability: float
>>>>>>> personal/main
    decision: Decision
    model_version: str
    trace_id: str


class HealthResponse(BaseModel):
<<<<<<< HEAD
    status: str


class ReadyResponse(BaseModel):
    status: str
=======
    status: Literal["ok"]
    service: str


class ReadyResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    status: Literal["ready", "loading"]
    model_version: str | None = None


class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    trace_id: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """Every non-2xx response has this shape - no stack traces, ever."""

    error: ErrorBody
>>>>>>> personal/main
