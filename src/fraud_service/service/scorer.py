from dataclasses import dataclass

<<<<<<< HEAD
from fraud_service.domain.entities import FraudScore, Transaction
=======
from fraud_service.domain.entities import (
    FraudScore,
    Transaction,
)
>>>>>>> personal/main
from fraud_service.domain.policies import decide
from fraud_service.service.interfaces import Model


@dataclass
class FraudScorer:
<<<<<<< HEAD
=======
    """Absent: no FastAPI, no sklearn, no file
    paths, no logging. Pure orchestration.
    """

>>>>>>> personal/main
    model: Model
    block_threshold: float

    def score(self, txn: Transaction) -> FraudScore:
        features = txn.to_features()
<<<<<<< HEAD
        probability = self.model.predict_proba(features)
        decision = decide(probability, self.block_threshold)
        return FraudScore(
            transaction_id=txn.transaction_id,
            probability=probability,
=======

        raw = self.model.predict_proba(features)

        decision = decide(
            raw,
            self.block_threshold,
        )

        return FraudScore(
            transaction_id=txn.transaction_id,
            probability=raw.value,
>>>>>>> personal/main
            decision=decision,
            model_version=self.model.model_version,
        )