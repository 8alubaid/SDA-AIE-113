from fraud_service.domain.entities import Decision

REVIEW_BAND = 0.15


def decide(probability: float, block_threshold: float) -> Decision:
    if probability >= block_threshold:
        return Decision.BLOCK
    if probability >= block_threshold - REVIEW_BAND:
        return Decision.REVIEW
    return Decision.ALLOW