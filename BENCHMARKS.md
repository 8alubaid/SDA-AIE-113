# Benchmarks

Load-test results for `POST /v1/predict`, measured with `hey` on the
machine described below. All numbers here are measured, not estimated.

## Environment

| | |
|---|---|
| OS | Windows 11, 12 logical CPUs |
| Python | 3.12.10 |
| FastAPI / Pydantic | 0.141.1 / 2.13.5 |
| scikit-learn | 1.9.0 |
| Server | `uvicorn`, single worker, `--log-level error` |
| Load generator | `hey`, same machine as the server |
| Model | `fraud_xgb_v3.joblib`, version `v3.2.0` |

Client and server share one machine, so the load generator competes with
the server for CPU. Absolute throughput is therefore a floor, not a
capacity figure for real hardware.

## Method

```
hey -n 2000 -c 50 -m POST -T application/json \
    -D payloads/sample.json http://127.0.0.1:8013/v1/predict
```

Each run starts a fresh server, waits for `/v1/health`, then issues an
untimed priming pass (`-n 200 -c 10`) before the measured run.

## Headline results — shipped configuration

Median of 5 runs, `def predict` (the code as committed):

| Metric | Value |
|---|---|
| **Requests/sec** | **139.4** |
| **p50 latency** | **346 ms** |
| **p99 latency** | **485 ms** |
| Errors | 0 — all 2000 responses `200` in every run |

## Startup warm-up

The `lifespan` hook issues one throwaway `predict_proba` before the service
reports ready, so the first real request does not pay for lazy
sklearn/numpy initialisation.

First-request latency, cold server, 3 runs each (`curl -w "%{time_total}"`):

| `WARMUP` | Run 1 | Run 2 | Run 3 | Median |
|---|---|---|---|---|
| `0` (off) | 53.7 ms | 65.9 ms | 60.4 ms | **60.4 ms** |
| `1` (on) | 17.5 ms | 13.2 ms | 14.4 ms | **14.4 ms** |

Warm-up removes roughly **46 ms** from the first request — about a 4x
improvement. The cost is paid once, at startup, before readiness.

## Experiment: `def` vs `async def` for the route handler

`scorer.score()` calls `predict_proba`, which is blocking CPU work. The
textbook expectation is that declaring the route `async def` runs that work
on the event loop, serialising concurrent requests and collapsing
throughput, while plain `def` hands it to a threadpool.

**That effect did not appear in these measurements.** Five interleaved runs
of each, alternating between variants to control for drift:

| Run | `def` rps | `async def` rps |
|---|---|---|
| 1 | 174.7 | 143.8 |
| 2 | 138.7 | 152.9 |
| 3 | 139.4 | 156.8 |
| 4 | 132.8 | 189.4 |
| 5 | 146.0 | 126.8 |
| **median** | **139.4** | **152.9** |

| Metric | `def` | `async def` |
|---|---|---|
| median rps | 139.4 | 152.9 |
| median p50 | 346 ms | 325 ms |
| median p99 | 485 ms | 486 ms |

The spread *within* each variant (`def` ranges 132.8-174.7; `async def`
ranges 126.8-189.4) is larger than the gap *between* the medians, and the
two ranges overlap almost completely. **This benchmark cannot distinguish
the two variants.** The median even favours `async def`, which is noise,
not a finding.

### Why the expected collapse is absent

A single-row `predict_proba` is short and largely GIL-bound Python work.
FastAPI's threadpool cannot parallelise GIL-bound work, so `def` gains
little from it; `async def` meanwhile avoids per-request threadpool
dispatch overhead. On this workload the two roughly cancel. The classic
collapse needs blocking work that is long relative to request overhead, or
that releases the GIL.

### The route still ships as `def`

Not because this benchmark proves it faster - it does not - but because it
is the choice that stays correct as the workload changes. If batch scoring,
a slower model, or any I/O is added later, `async def` would serialise all
of it on the event loop, while `def` degrades gracefully. `def` is the safe
default; this measurement simply shows the penalty is not yet visible at
this scale.

## Reproducing

```
hey -n 2000 -c 50 -m POST -T application/json \
    -D payloads/sample.json http://127.0.0.1:8000/v1/predict
```

Disable startup warm-up for comparison with `WARMUP=0`.
