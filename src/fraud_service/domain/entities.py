<<<<<<< HEAD
"""Domain entities: the vocabulary of the fraud problem.

Rule for this file: imports from stdlib + pydantic ONLY. No pandas, no
sklearn, no joblib.
"""
import math
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Channel(StrEnum):
    POS = "pos"
    ECOM = "ecom"
    ATM = "atm"
    TRANSFER = "transfer"


class Transaction(BaseModel):
    transaction_id: str
    amount_sar: float = Field(gt=0)
    channel: Channel
    merchant_category: str
    customer_id: str
    timestamp: datetime

    def to_features(self) -> "FeatureVector":
        """The ONE place feature logic lives — this is what cell 9 of the
        notebook broke, by recomputing amount_log a second, different way."""
        return FeatureVector(values={
            "amount_log": math.log1p(self.amount_sar),
            "channel": self.channel.value,
            "mcc": self.merchant_category.strip().upper().replace(" ", "_"),
            "hour_of_day": self.timestamp.hour,
            "is_night": int(self.timestamp.hour < 6),
        })


class FeatureVector(BaseModel):
    values: dict[str, float | int | str]


class Decision(StrEnum):
=======
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
>>>>>>> personal/main
    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"

<<<<<<< HEAD
class FraudScore(BaseModel):
=======

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
>>>>>>> personal/main
    transaction_id: str
    probability: float
    decision: Decision
    model_version: str