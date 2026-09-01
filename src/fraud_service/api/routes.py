<<<<<<< HEAD
import time
=======
"""HTTP routes.

Thin by design: parse -> delegate -> shape the response. No business rules
live here; they are in `domain/policies.py`.
"""
from typing import Annotated
>>>>>>> personal/main

from fastapi import APIRouter, Depends, HTTPException, Request

from fraud_service.api.schemas import (
    HealthResponse,
    PredictRequest,
    PredictResponse,
    ReadyResponse,
)
<<<<<<< HEAD
from fraud_service.logging_setup import get_logger
from fraud_service.service.scorer import FraudScorer

log = get_logger(__name__)
router = APIRouter()


def get_scorer(request: Request) -> FraudScorer:
    """DI seam: Lab 4's tests override this one function to inject a fake
    model - no real sklearn artefact needed to test the API contract."""
    scorer: FraudScorer | None = getattr(request.app.state, "scorer", None)
    if scorer is None:                       # startup incomplete/failed
        raise HTTPException(status_code=503, detail="Model not ready",
                            headers={"Retry-After": "5"})
    return scorer


# NOT async def - sklearn inference is CPU-bound. FastAPI runs plain `def`
# routes in a thread pool automatically; `async def` here would run the
# CPU-bound call directly on the single event loop and block every other
# in-flight request until it finishes.
@router.post("/predict", response_model=PredictResponse)
def predict(body: PredictRequest, request: Request,
           scorer: FraudScorer = Depends(get_scorer)) -> PredictResponse:
    t0 = time.perf_counter()
    score = scorer.score(body.to_domain())
    log.info("prediction_served",
             decision=score.decision.value,
             probability_bucket=round(score.probability, 1),  # bucketed - never raw+id together
             model_version=score.model_version,
             latency_ms=round((time.perf_counter() - t0) * 1000, 1))
    # ABSENT by design: customer_id, amount, raw feature values
=======
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
>>>>>>> personal/main

    return PredictResponse(
        transaction_id=score.transaction_id,
        fraud_probability=round(score.probability, 6),
        decision=score.decision,
        model_version=score.model_version,
        trace_id=request.state.trace_id,
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
<<<<<<< HEAD
    """Liveness: is the process alive? NO I/O here - ever."""
    return HealthResponse(status="ok")
=======
    """Liveness: is this process alive? Never touches the model."""
    return HealthResponse(status="ok", service="fraud-service")
>>>>>>> personal/main


@router.get("/ready", response_model=ReadyResponse)
def ready(request: Request) -> ReadyResponse:
<<<<<<< HEAD
    """Readiness: can I serve correctly RIGHT NOW? Checks the model loaded."""
    if getattr(request.app.state, "scorer", None) is None:
        raise HTTPException(status_code=503, detail="warming up")
    return ReadyResponse(status="ready")
=======
    """Readiness: can this process actually serve traffic?"""
    scorer = getattr(request.app.state, "scorer", None)
    if scorer is None:
        raise _NOT_READY

    return ReadyResponse(
        status="ready",
        model_version=scorer.model.model_version,
    )
>>>>>>> personal/main
