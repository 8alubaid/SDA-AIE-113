from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from fraud_service.api.app import create_app
from fraud_service.api.routes import get_scorer
from fraud_service.domain.entities import FeatureVector, Transaction
from fraud_service.service.scorer import FraudScorer


class ConstantModel:
    def __init__(self, p: float, version: str ="test-1"):
        self._p , self.model_version = p , version

    def predict_proba(self, features: FeatureVector) -> float:
        return self._p


@pytest.fixture
def sample_txn() -> Transaction:
    return Transaction(
        transaction_id="TXN-TEST-0001", amount_sar=250.0, channel="ecom",
        merchant_category="electronics", customer_id="CUST-77",
        timestamp=datetime(2026,7,5,3,30, tzinfo=UTC)
    )

@pytest.fixture
def client_factory():
    def _make(probability: float = 0.10, threshhold: float = 0.85) -> TestClient:
        app = create_app()
        scorer = FraudScorer(model=ConstantModel(probability), block_threshold=threshhold)
        app.dependency_overrides[get_scorer] = lambda: scorer
        return TestClient(app, raise_server_exceptions=False)
    return _make


@pytest.fixture(scope="session")
def real_model():
    from pathlib import Path

    from fraud_service.adapters.sklearn_model import SklearnModel
    return SklearnModel.load(Path("models/fraud_xgb_v3.joblib"))


