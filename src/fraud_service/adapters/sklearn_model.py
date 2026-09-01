<<<<<<< HEAD
from pathlib import Path

import joblib
import pandas as pd

from fraud_service.domain.entities import FeatureVector


class SklearnModel:
    def __init__(self, pipeline, model_version: str) -> None:
        self._pipeline = pipeline
        self.model_version = model_version

    @classmethod
    def load(cls, path: Path) -> "SklearnModel":
        bundle = joblib.load(path)
        return cls(bundle["pipeline"], bundle["version"])

    def predict_proba(self, features: FeatureVector) -> float:
        frame = pd.DataFrame([features.values])
        return float(self._pipeline.predict_proba(frame)[0, 1])
=======
import joblib
import pandas as pd

from fraud_service.domain.entities import (
    FeatureVector,
    RawScore,
)


class SklearnModel:
    def __init__(
        self,
        pipeline,
        model_version: str,
    ) -> None:
        self.pipeline = pipeline
        self.model_version = model_version

    @classmethod
    def load(cls, path: str) -> "SklearnModel":
        bundle = joblib.load(path)

        return cls(
            pipeline=bundle["pipeline"],
            model_version=bundle["version"],
        )

    def predict_proba(
        self,
        features: FeatureVector,
    ) -> RawScore:
        frame = pd.DataFrame(
            [
                {
                    "amount_log": features.amount_log,
                    "channel": features.channel,
                    "mcc": features.mcc,
                    "hour_of_day": features.hour_of_day,
                    "is_night": features.is_night,
                }
            ]
        )

        probability = self.pipeline.predict_proba(frame)[0, 1]

        return RawScore(
            value=float(probability)
        )
>>>>>>> personal/main
