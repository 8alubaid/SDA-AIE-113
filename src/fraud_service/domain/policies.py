"""Business policy: thresholds are BUSINESS
decisions, not model decisions.

Pure function => property-based-testable,
reviewable by risk officers."""
from fraud_service.domain.entities import (
    Decision,
    RawScore,
)

REVIEW_BAND = 0.15  # manual-review band width


def decide(score: RawScore,
           block_threshold: float) -> Decision:
    if score.value >= block_threshold:
        return Decision.BLOCK
    if score.value >= block_threshold - REVIEW_BAND:
        return Decision.REVIEW
    return Decision.ALLOW
