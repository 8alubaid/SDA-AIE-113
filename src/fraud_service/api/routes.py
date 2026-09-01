"""HTTP routes.

Thin by design: parse -> delegate -> shape the response. No business rules
live here; they are in `domain/policies.py`.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from fraud_service.api.schemas import (
    HealthResponse,
    PredictRequest,
    PredictResponse,
    ReadyResponse,
)
from fraud_service.service.scorer import FraudScorer

router = APIRouter(tags=["fraud"])

_NOT_READY = HTTPException(
    status_code=503,
    detail="Model not ready",
    headers={"Retry-After": "5"},
)


def get_scorer(request: Request) -> FraudScorer:
    scorer = getattr(request.app.state, "scorer", None)
    if scorer is None:
        # startup incomplete/failed
        raise _NOT_READY
    return scorer


ScorerDep = Annotated[FraudScorer, Depends(get_scorer)]


@router.post("/predict", response_model=PredictResponse)
def predict(
    body: PredictRequest,
    request: Request,
    scorer: ScorerDep,
) -> PredictResponse:
    """Score one transaction.

    Deliberately `def`, not `async def`: `predict_proba` is blocking CPU
    work, so FastAPI runs this in a threadpool. Declaring it `async` would
    park that work on the event loop and stall every concurrent request.
    """
    score = scorer.score(body.to_domain())

    return PredictResponse(
        transaction_id=score.transaction_id,
        fraud_probability=round(score.probability, 6),
        decision=score.decision,
        model_version=score.model_version,
        trace_id=request.state.trace_id,
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness: is this process alive? Never touches the model."""
    return HealthResponse(status="ok", service="fraud-service")


@router.get("/ready", response_model=ReadyResponse)
def ready(request: Request) -> ReadyResponse:
    """Readiness: can this process actually serve traffic?"""
    scorer = getattr(request.app.state, "scorer", None)
    if scorer is None:
        raise _NOT_READY

    return ReadyResponse(
        status="ready",
        model_version=scorer.model.model_version,
    )