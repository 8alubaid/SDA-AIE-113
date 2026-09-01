from typing import Protocol

from fraud_service.domain.entities import FeatureVector


class Model(Protocol):
    """Anything that can turn features into a probability. No inheritance
    needed - the adapter satisfies this just by having the right method
    signature. This is the whole seam: the service layer never imports
    sklearn, joblib, or pandas - only this Protocol."""
    model_version: str

    def predict_proba(self, features: FeatureVector) -> float: ...