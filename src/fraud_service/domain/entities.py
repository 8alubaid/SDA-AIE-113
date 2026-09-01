import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


@dataclass(frozen=True)
class FeatureVector:
    amount_log: float
    channel: str
    mcc: str
    hour_of_day: int
    is_night: int


@dataclass(frozen=True)
class RawScore:
    value: float


class Decision(str, Enum):
    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"


@dataclass(frozen=True)
class Transaction:
    transaction_id: str
    amount_sar: float
    channel: str
    merchant_category: str
    timestamp: datetime

    def to_features(self) -> FeatureVector:
        hour_of_day = self.timestamp.hour

        return FeatureVector(
            amount_log=math.log1p(self.amount_sar),
            channel=self.channel,
            mcc=self.merchant_category.strip().upper().replace(" ", "_"),
            hour_of_day=hour_of_day,
            is_night=int(hour_of_day < 6),
        )


@dataclass(frozen=True)
class FraudScore:
    transaction_id: str
    probability: float
    decision: Decision
    model_version: str