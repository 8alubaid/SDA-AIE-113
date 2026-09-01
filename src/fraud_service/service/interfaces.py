from typing import Protocol

from fraud_service.domain.entities import (
    FeatureVector,
    RawScore,
)


class Model(Protocol):
    """Anything that can score a feature vector.

    Implementations: SklearnModel (prod),
    ConstantModel (tests), RemoteModel (future).
    The service layer knows ONLY this signature."""

    model_version: str

    def predict_proba(
        self, features: FeatureVector
    ) -> RawScore: ...
