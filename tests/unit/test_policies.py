import pytest

from fraud_service.domain.entities import Decision
from fraud_service.domain.policies import decide


@pytest.mark.unit
@pytest.mark.parametrize("p, expected", [
    (0.849999, Decision.REVIEW),
    (0.85,     Decision.BLOCK),
    (0.699999, Decision.ALLOW),
    (0.70,     Decision.REVIEW),
    (0.0,      Decision.ALLOW),
    (1.0,      Decision.BLOCK),
])
def test_decision_bands(p, expected):
    assert decide(p, block_threshold=00.85) is expected

    