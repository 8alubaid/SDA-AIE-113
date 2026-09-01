# Engineering decisions

A record of the trade-offs made while refactoring `notebook_v1.ipynb` into the
service in `src/fraud_service/`. Each entry states the options that were on the
table, what was chosen, the concrete reason, and what the choice costs.

Decisions are listed roughly in the order they were made.

---

## D1 — Feature derivation lives in exactly one method

**Context.** In the notebook, `amount_log` is computed in cell 5 with
`math.log1p(x)`, and then recomputed in cell 9 with `math.log10(x + 1)` — a
different formula, written into the same column, in the same file.

**Options considered**

1. Keep feature code inline at each call site; rely on discipline and review.
2. Put the feature list in a shared constant, keep the maths at each call site.
3. Derive features in a single method on the domain entity, and give no caller a
   way to compute them any other way.

**Decision.** Option 3 — `Transaction.to_features()` in
`src/fraud_service/domain/entities.py` is the only place feature logic exists.
Batch scoring and online serving both go through it.

**Why.** Executing the notebook end to end makes the cost of the alternative
measurable. The first scoring pass, on correctly derived features, produces:

```
allow 4369   review 320   block 311
```

The second pass — same model, same rows, after `amount_log` has been silently
overwritten with the log10 variant — produces:

```
allow 4719   review 158   block 1
```

Fraud blocks collapse from **311 to 1**. Nothing errored, nothing warned; the
notebook just quietly stopped catching fraud. That is training/serving skew
self-inflicted inside a single file, and no amount of review discipline reliably
prevents it. Making the derivation a single method makes the failure
unrepresentable rather than merely discouraged.

**Cost.** Feature changes now require touching a domain entity and its tests,
which is slower than editing a cell. That friction is the point.

---

## D2 — The model loads in `lifespan`, not at import time

**Context.** Notebook cell 1 calls `joblib.load(...)` at module scope, so
importing the module loads a model.

**Options considered**

1. Load at import time (what the notebook does).
2. Load lazily, on the first request that needs it.
3. Load once during application startup, in the FastAPI `lifespan` hook.

**Decision.** Option 3, in `src/fraud_service/api/app.py`.

**Why.** Import-time loading means every consumer pays the cost — the test
suite, a linter that imports the module, a CLI that only wants one helper — and
there is no place to handle a load failure. Lazy loading moves the cost onto a
real customer's first request and makes readiness meaningless: the process
reports healthy before it can actually serve.

Loading in `lifespan` gives one well-defined moment where the artefact is read,
where a failure aborts startup rather than surfacing as a 500, and after which
readiness is truthful.

**Cost.** Startup is slower — about 2.8 s in local runs — and that time is
visible in deployment rolling-update windows. This is the right place to pay it.

---

## D3 — Warm the model up before reporting ready

**Context.** scikit-learn and numpy do a significant amount of lazy
initialisation on the first `predict_proba` call.

**Options considered**

1. Report ready as soon as the artefact is deserialised.
2. Issue one throwaway prediction during startup, before reporting ready.

**Decision.** Option 2 — `_warmup_features()` builds a synthetic transaction and
the lifespan hook scores it before yielding.

**Why.** Measured, on a cold server, median of three runs
(see [`BENCHMARKS.md`](BENCHMARKS.md)):

| Warm-up | Median first-request latency |
| ------- | ---------------------------- |
| off     | 60.4 ms                      |
| on      | 14.4 ms                      |

Roughly 46 ms — about 4x — removed from the first real request, paid once at
startup while the orchestrator is still waiting for readiness anyway.

**Cost.** Startup is marginally longer, and the warm-up transaction is a
hardcoded synthetic record that has to stay valid as the schema evolves.

---

## D4 — `/v1/predict` is a plain `def`, not `async def`

**Context.** FastAPI runs `async def` handlers on the event loop and plain `def`
handlers in a threadpool. `scorer.score()` calls `predict_proba`, which is
blocking CPU work.

**Options considered**

1. `async def` — the default reflex for a modern Python web framework.
2. Plain `def`, letting FastAPI offload to its threadpool.

**Decision.** Option 2.

**Why.** An `async def` handler doing blocking CPU work occupies the single
event loop for the duration of that work, stalling every other in-flight
request — including the health and readiness probes that decide whether the
container stays alive.

**What the measurement actually showed.** This was benchmarked rather than
assumed, and the expected effect **did not appear**. Across five interleaved runs
of each variant at 2000 requests / concurrency 50, `async def` was, if anything,
marginally faster (median 152.9 rps vs 139.4 rps for `def`). The numbers are
recorded in [`BENCHMARKS.md`](BENCHMARKS.md) as they came out.

The handler stays a plain `def` anyway: the benchmark ran with client and server
competing for the same 12 CPUs, which is precisely the regime where the
threadpool's advantage is masked. The reasoning holds under load this benchmark
did not reach, and the failure mode it prevents — probes timing out behind a
blocked event loop — is severe and hard to diagnose. Keeping a decision that the
local benchmark did not vindicate is itself the trade-off being recorded here.

**Cost.** Threadpool dispatch adds per-request overhead, and the threadpool size
becomes a capacity limit that has to be tuned under real load.

---

## D5 — The validation error envelope is rebuilt, not passed through

**Context.** FastAPI's default `RequestValidationError` handler echoes the raw
offending input value back to the client.

**Options considered**

1. Use FastAPI's default handler.
2. Override it and re-emit only fields known to be JSON-safe.

**Decision.** Option 2 — the handler in `app.py` rebuilds each error as
`{"loc", "msg", "type"}` and deliberately drops the echoed `input` value.

**Why.** Two distinct problems with the default:

- **Correctness.** A payload containing `Infinity` or `NaN` — Python's JSON
  parser accepts both — produces an offending value that is not JSON-serialisable
  on the way back out. The 422 then fails to serialise and becomes a 500: a
  validation failure turned into a server error, and an availability problem
  reachable by anyone who can POST. `payloads/malformed/amount_infinity.json`
  exists specifically to hold this case, and the integration suite asserts it
  stays in the 4xx range.
- **Disclosure.** Echoing raw input reflects attacker-controlled content back
  into the response body, and on a fraud endpoint that input is customer data.

**Cost.** Clients lose the "you sent X" hint. `loc`, `msg`, and `type` still
identify the offending field precisely, which is enough to fix a bad request.

---

## D6 — The container healthcheck targets `/v1/ready`, not `/v1/health`

**Context.** Two probes exist and they answer different questions. `/v1/health`
asks "is the process alive?" and performs no I/O. `/v1/ready` asks "can I serve
correctly right now?" and returns 503 until the model is loaded.

**Options considered**

1. Point the healthcheck at `/v1/health`.
2. Point it at `/v1/ready`.
3. Expose one combined endpoint.

**Decision.** Option 2, with `--start-period=20s` in the Dockerfile.

**Why.** Option 3 forces a single answer to two questions with opposite failure
responses. If a liveness probe checks the model, then a slow model load looks
like a dead process: the orchestrator kills the container, the replacement is
also slow to load, and the service never starts — a restart loop caused entirely
by the probe. If a readiness probe ignores the model, traffic is routed to a
process that cannot answer it.

Keeping them separate means a slow start delays traffic (correct) instead of
killing the container (catastrophic). The CI `image-smoke` job polls `/v1/ready`
before sending its test payload for the same reason.

**Cost.** Two endpoints to maintain, and a real obligation not to let I/O drift
into the liveness path.

---

## D7 — The service layer depends on a `Protocol`, not on scikit-learn

**Context.** Something has to turn a `FeatureVector` into a probability, and
that something is a joblib-pickled sklearn pipeline fed by a pandas DataFrame.

**Options considered**

1. Have `FraudScorer` import and call `SklearnModel` directly.
2. Define an abstract base class for models and inherit from it.
3. Define a `Protocol` and let any object with the right shape satisfy it.

**Decision.** Option 3 — `Model` in `src/fraud_service/service/interfaces.py`
declares `model_version` and `predict_proba`; `SklearnModel` satisfies it
structurally, without importing or inheriting anything.

**Why.** This is the seam the entire test strategy rests on. `ConstantModel` in
`tests/conftest.py` is eleven lines with no sklearn, no joblib, and no artefact
on disk, and it makes the whole HTTP contract testable — the integration suite,
including all 43 malformed payloads, runs against a fake model injected through
`app.dependency_overrides`. The full fast suite finishes in about 6 seconds.

An ABC would have worked too, but would force the adapter to import from the
service layer purely to declare a relationship the type checker can already
infer. A `Protocol` keeps the dependency arrow pointing one way, which is what
`import-linter` enforces in CI.

**Cost.** Protocol conformance is checked by mypy, not at runtime, so a
mismatched adapter fails later than an ABC's would.

---

## D8 — Two lint rules are suppressed narrowly, with reasons recorded

**Context.** Two ruff rules fire on code that is correct as written.

**`B008` — function call in an argument default**

- *Options:* rewrite as `Annotated[FraudScorer, Depends(get_scorer)]`; suppress
  globally; suppress for the one file.
- *Decision:* per-file ignore in `pyproject.toml`, scoped to
  `src/fraud_service/api/routes.py`.
- *Why:* `Depends(...)` in a parameter default is FastAPI's own documented
  idiom, and it is exactly what makes `get_scorer` overridable in tests. The
  rule is right in general and wrong here. Scoping the exemption to one file
  keeps it enforced everywhere else.

**`TRY004` — prefer `TypeError` for a type check**

- *Options:* change the raise to `TypeError`; suppress on the line.
- *Decision:* keep `ValueError`, suppress on the line with the reason inline.
- *Why:* pydantic converts only `ValueError` and `AssertionError` into a
  `ValidationError`. A `TypeError` raised inside a validator escapes it, so
  `payloads/malformed/amount_as_bool.json` would return 500 instead of 422 —
  following the linter would have introduced the exact bug the validator exists
  to prevent. Booleans need rejecting at all because `bool` subclasses `int` in
  Python, so JSON `true` would otherwise coerce to `1.0` and pass the `gt=0`
  and `le=1_000_000` checks.

**Cost.** Every suppression is a small permanent exception that a future reader
has to evaluate. Both are one line, scoped as tightly as the tool allows, and
carry their reason next to them.

---

## D9 — Scores are logged bucketed, and never beside an identifier

**Context.** The `prediction_served` event is the main operational signal for
the endpoint.

**Options considered**

1. Log the full request and response — easiest to debug.
2. Log the score with the customer and transaction IDs for traceability.
3. Log the decision, a bucketed probability, the model version, and the latency;
   correlate everything else through a per-request trace ID.

**Decision.** Option 3, plus a structlog processor that masks any key named like
a secret (`password`, `token`, `secret`, `authorization`, `national_id`,
`card_number`).

**Why.** A raw fraud score next to a customer ID is a per-customer risk profile
sitting in a log aggregator, replicated to wherever logs ship, under a retention
policy the application does not control. Rounding the probability to one decimal
keeps the distribution monitorable without making any single line a disclosure.
The `trace_id` — returned to the client as `X-Trace-Id` and bound to every line
of that request — preserves the ability to investigate one specific request
without storing the sensitive join.

**Cost.** Debugging a single mis-scored transaction from logs alone is harder;
it requires the trace ID rather than a grep for the customer.

---

## D10 — The block threshold is validated configuration, not a constant

**Context.** The notebook sets `BLOCK_THRESHOLD` from an environment variable in
cell 5, then reassigns it to `0.80` in cell 11 — "felt right after looking at the
review-band counts above".

**Options considered**

1. Hardcode the threshold in the policy module.
2. Read `os.environ` where it is needed.
3. One typed `Settings` object, validated at startup, as the only reader of the
   environment.

**Decision.** Option 3 — `src/fraud_service/config.py`, with `env_prefix="FRAUD_"`
and `extra="forbid"`.

**Why.** The threshold is a risk-approved business boundary, not a tuning knob:
it needs to be visible, bounded, and auditable. `Settings` constrains it to
`0.5 <= x <= 0.99`, so a fat-fingered `0.085` fails at boot rather than silently
approving everything. `extra="forbid"` means a misspelled `FRAUD_BLOCK_THRESHOLDD`
crashes instead of being ignored while the default quietly stays in force — the
failure mode that is hardest to notice in production. `model_path` is validated
for existence at startup for the same reason: a missing artefact should abort
the deploy, not 500 on the first customer.

The effective configuration is logged once at startup, values but never secrets,
so an incident responder can see what the process actually loaded.

**Cost.** Configuration changes now require a restart, and the settings object
is a module every layer indirectly depends on.

---

## D11 — Multi-stage image, non-root runtime

**Context.** `Dockerfile.naive` is kept in the repository as the baseline: a
single stage that copies the whole build context and installs in place.

**Options considered**

1. Single-stage build (`Dockerfile.naive`).
2. Multi-stage build, with a virtualenv copied into a clean runtime layer.

**Decision.** Option 2, running as `appuser` (uid 10001).

**Why.** The naive image ships `build-essential`, pip's caches, the test suite,
the notebook, and the raw CSVs — attack surface and image size that serve no
runtime purpose. The multi-stage build leaves compilers in the builder stage and
copies only `/opt/venv` and the model artefact into the runtime image. Running
as a non-root user means a process compromise does not start as root, and
`.dockerignore` keeps `tests/`, `data/`, and the notebook out of the context
entirely.

**Cost.** The Dockerfile is longer and less obvious, and the dependency list is
duplicated in the builder stage rather than resolved from `pyproject.toml`.

---

## Open items

Recorded honestly rather than quietly left out; see the README's *Known issues*
for the same list.

- `make run-batch` crashes: `batch.py` reads `.value` from a `FraudScore` as
  though it were a `Decision`. The HTTP path is unaffected.
- `mypy --strict` reports 16 errors, mostly missing annotations on FastAPI
  lifespan, middleware, and validator callables. `ruff` and `lint-imports` pass.
- The Compose healthcheck URL uses backslashes, so `fraud-api` never reports
  healthy under `docker compose`. Running the image directly is unaffected.
