from dataclasses import dataclass

from fraud_service.domain.entities import (
    FraudScore,
    Transaction,
)
from fraud_service.domain.policies import decide
from fraud_service.service.interfaces import Model


@dataclass
class FraudScorer:
    """Absent: no FastAPI, no sklearn, no file
    paths, no logging. Pure orchestration.
    """

    model: Model
    block_threshold: float

    def score(self, txn: Transaction) -> FraudScore:
        features = txn.to_features()

        raw = self.model.predict_proba(features)

        decision = decide(
            raw,
            self.block_threshold,
        )

        return FraudScore(
            transaction_id=txn.transaction_id,
            probability=raw.value,
            decision=decision,
            model_version=self.model.model_version,
        )