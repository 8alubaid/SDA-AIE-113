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
    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"

class FraudScore(BaseModel):
    transaction_id: str
    probability: float
    decision: Decision
    model_version: str