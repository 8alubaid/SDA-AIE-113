<<<<<<< HEAD
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
=======
"""FastAPI application factory.

The composition root for the API, exactly as `batch.py` is for the batch
job: this is the only place that knows about file paths, env config and
concrete model classes.
"""
import math
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
>>>>>>> personal/main

from fraud_service.adapters.sklearn_model import SklearnModel
from fraud_service.api.routes import router
from fraud_service.config import Settings
<<<<<<< HEAD
from fraud_service.logging_setup import configure_logging, get_logger
from fraud_service.service.scorer import FraudScorer

log = get_logger(__name__)
=======
from fraud_service.domain.entities import FeatureVector
from fraud_service.observability import configure_logging, log
from fraud_service.service.scorer import FraudScorer

TRACE_HEADER = "X-Trace-Id"
TIMING_HEADER = "X-Response-Time-Ms"


def _warmup_features() -> FeatureVector:
    """A representative vector, used to force lazy work at startup.

    The first `predict_proba` pays for sklearn/numpy warm-up. Doing it here
    means the cost lands before the service reports ready, not on a real
    customer's first request.
    """
    return FeatureVector(
        amount_log=math.log1p(100.0),
        channel="ecom",
        mcc="GROCERY",
        hour_of_day=12,
        is_night=0,
    )
>>>>>>> personal/main


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    configure_logging(settings.log_level)
<<<<<<< HEAD
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
=======

    t0 = time.perf_counter()
    model = SklearnModel.load(settings.model_path)
    if settings.warmup:
        model.predict_proba(_warmup_features())  # warm-up
    log.info(
        "model_loaded",
        version=model.model_version,
        seconds=round(time.perf_counter() - t0, 3),
        warmup=settings.warmup,
    )

    app.state.scorer = FraudScorer(
        model=model,
        block_threshold=settings.block_threshold,
    )
    app.state.started_at = datetime.now(UTC)

    yield

    log.info("shutdown_complete")


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "unavailable")


def _envelope(
    status_code: int,
    code: str,
    message: str,
    trace_id: str,
    details: list[dict[str, str]] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "trace_id": trace_id,
                "details": details or [],
            }
        },
        headers={TRACE_HEADER: trace_id},
    )


def _field_name(loc: tuple[Any, ...]) -> str:
    """Render a pydantic error location as a client-facing field name.

    A JSON decode error arrives as `("body", 0)` - a character offset, not a
    field - so anything purely positional collapses to `<body>`.
    """
    parts = [str(p) for p in loc if p != "body"]
    if not parts or all(p.isdigit() for p in parts):
        return "<body>"
    return ".".join(parts)


async def _handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {"field": _field_name(err["loc"]), "message": err["msg"]}
        for err in exc.errors()
    ]
    log.warning(
        "request_rejected",
        trace_id=_trace_id(request),
        path=request.url.path,
        fields=[d["field"] for d in details],
    )
    return _envelope(
        422,
        "validation_error",
        "Request failed validation",
        _trace_id(request),
        details,
    )


async def _handle_http_error(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    response = _envelope(
        exc.status_code,
        "not_ready" if exc.status_code == 503 else "http_error",
        str(exc.detail),
        _trace_id(request),
    )
    for key, value in (exc.headers or {}).items():
        response.headers[key] = value
    return response


async def _handle_unexpected_error(
    request: Request, exc: Exception
) -> JSONResponse:
    """Last line of defence: a stack trace must never reach the client.

    The traceback goes to the log, keyed by trace id; the caller gets that
    id and nothing else.
    """
    log.error(
        "unhandled_exception",
        exc_info=True,
        trace_id=_trace_id(request),
        path=request.url.path,
    )
    return _envelope(
        500,
        "internal_error",
        "Internal server error",
        _trace_id(request),
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title="Fraud Scoring Service",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def trace_and_time(request: Request, call_next: Any):
        trace_id = request.headers.get(TRACE_HEADER) or uuid4().hex[:16]
        request.state.trace_id = trace_id

        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000

        response.headers[TRACE_HEADER] = trace_id
        response.headers[TIMING_HEADER] = f"{elapsed_ms:.2f}"

        log.info(
            "request_completed",
            trace_id=trace_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            ms=round(elapsed_ms, 2),
        )
        return response

    app.add_exception_handler(
        RequestValidationError, _handle_validation_error
    )
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)

    app.include_router(router, prefix="/v1")
    return app


app = create_app()
>>>>>>> personal/main
