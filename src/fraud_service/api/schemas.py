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
    decision: Decision
    model_version: str
    trace_id: str


class HealthResponse(BaseModel):
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
