"""The composition root for the API - same idea as batch.py's main(),
now for the HTTP entrypoint. The model loads ONCE, here, in lifespan -
never at import time, never per-request."""
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from fraud_service.adapters.sklearn_model import SklearnModel
from fraud_service.api.routes import router
from fraud_service.config import Settings
from fraud_service.logging_setup import configure_logging, get_logger
from fraud_service.service.scorer import FraudScorer

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    configure_logging(settings.log_level)
    # Effective-config visibility: one line, never secrets, huge payoff
    # during an incident (this is what catches config-drift).
    log.info("effective_config", block_threshold=settings.block_threshold,
             model_path=str(settings.model_path), log_level=settings.log_level)

    t0 = time.perf_counter()
    model = SklearnModel.load(settings.model_path)   # fail fast if absent
    # Warm-up: pay the lazy-init cost now, not on the first real user request.
    model.predict_proba(_warmup_features())
    log.info("model_loaded", version=model.model_version,
             seconds=round(time.perf_counter() - t0, 3))

    app.state.scorer = FraudScorer(model=model, block_threshold=settings.block_threshold)
    app.state.settings = settings
    yield
    log.info("shutdown_complete")


def create_app() -> FastAPI:
    app = FastAPI(title="Fraud Scoring Service", lifespan=lifespan)
    app.include_router(router, prefix="/v1")

    @app.middleware("http")
    async def trace_and_time(request: Request, call_next):
        trace_id = uuid.uuid4().hex[:16]
        request.state.trace_id = trace_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(trace_id=trace_id, path=request.url.path)

        t0 = time.perf_counter()
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        response.headers["X-Trace-Id"] = trace_id
        response.headers["X-Response-Time-Ms"] = str(latency_ms)
        log.info("http_request", status=response.status_code, latency_ms=latency_ms)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI's default handler echoes the raw offending value back to
        # the client - if that value is a non-JSON-safe float (inf/nan),
        # serialising it can turn a validation failure into a 500.
        # Stringify every field instead of trusting it's JSON-safe.
        errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]}
                 for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})

    return app


def _warmup_features():
    from datetime import datetime

    from fraud_service.domain.entities import Transaction
    return Transaction(
        transaction_id="WARMUP-0000", amount_sar=100.0, channel="pos",
        merchant_category="GROCERY", customer_id="warmup",
        timestamp=datetime.now(UTC)).to_features()


app = create_app()