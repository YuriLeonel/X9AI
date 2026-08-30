# server-api Design

**Spec**: `.specs/features/server-api/spec.md`
**Status**: Approved

---

## Architecture Overview

A thin FastAPI service exposing the single `POST /process` boundary. The HTTP layer talks
only to a `Pipeline` protocol (AD-004: single combined interface, complete swap). The
pipeline is a deterministic stub in this feature; `nlp-pipeline` swaps the default later
without touching the HTTP layer.

```mermaid
graph TD
    C[Client / TestClient / curl] -->|POST /process multipart| R[POST /process handler]
    R --> V[Metadata parse + validations]
    V -->|bytes + language| P[Pipeline protocol]
    P --> S[StubPipeline]
    R -->|elapsed ms| L[structured log line]
    R -->|Success| SRes[{"status":"success",...}]
    R -->|Error| ERes[mapped generic error JSON]
```

**Approach exploration.** Three viable shapes; **Approach A chosen.**

- **A — App-factory + protocol seam** (chosen): `create_app(pipeline: Pipeline | None = None)`
  builds the FastAPI app and injects the seam. KISS: one seam, one route, no DI container.
  Tests build `create_app(pipeline=StubPipeline())` for determinism. YAGNI-clean.
- **B — FastAPI `Depends` dependency-injection container**: more ceremony, a `dependencies`
  module and overrides machinery that a 1-endpoint service does not need. Rejected.
- **C — Single-file `main.py` monolith**: fewest files but no seam boundary and poor test
  isolation as `nlp-pipeline`/`golden-oracle` land. Rejected.

## Code Reuse Analysis

### Existing Components to Leverage

| Component | Location | How to Use |
| --------- | -------- | ---------- |
| (none — greenfield) | — | First code in the repo |

### Integration Points

| System | Integration Method |
| ------ | ------------------ |
| Client (future) | HTTP `POST /process`, JSON body contract `docs/spec.md` §6 |
| `nlp-pipeline` (future) | Implements `Pipeline` protocol; swapped as the default in `create_app` |

---

## Components

### `x9ai/pipeline` — the seam

- **Purpose**: Defines the single swappable transcription+normalization boundary (AD-004).
- **Location**: `server/x9ai/pipeline.py`
- **Interfaces**:
  - `class Pipeline(ABC)`: `process(self, audio: bytes, language: str) -> str` — abstract.
  - `class StubPipeline(Pipeline)`: deterministic `"stub:<lang>:<len>"` output for contract tests.
- **Dependencies**: `abc` only.
- **Reuses**: none.

### `x9ai/schemas` — response contract

- **Purpose**: Exact JSON shapes from `docs/spec.md` §6.2, enforced at the type level.
- **Location**: `server/x9ai/schemas.py`
- **Interfaces**: `SuccessResponse(status: Literal["success"], text: str, processing_time_ms: int)`; `ErrorResponse(status: Literal["error"], message: str)`
- **Dependencies**: pydantic (ships with FastAPI).
- **Reuses**: none.

### `x9ai/config` — settings

- **Purpose**: Single source of env-overridable runtime bounds.
- **Location**: `server/x9ai/config.py`
- **Interfaces**: `@dataclass(frozen=True) Settings: max_audio_bytes: int;` + `Settings.from_env()` reads `MAX_AUDIO_BYTES`.
- **Dependencies**: `os`, `dataclasses`.
- **Reuses**: none.

### `x9ai/logs` — observability

- **Purpose**: One structured line per handled request (§4.1 server-side diagnostics; SRV-11).
- **Location**: `server/x9ai/logs.py`
- **Interfaces**: `configure_logging() -> logging.Logger` (module logger `x9ai`); helper `log_request(...)` emitting `method= path= status= processing_time_ms= client_timestamp=`.
- **Dependencies**: `logging`.
- **Reuses**: none.

### `x9ai/app` — HTTP boundary

- **Purpose**: The one endpoint + error mapping; owns multipart parsing, validation, timing.
- **Location**: `server/x9ai/app.py`
- **Interfaces**: `create_app(pipeline: Pipeline | None = None) -> FastAPI`; route `POST /process` (`audio_file: UploadFile`, `metadata: str | None`).
- **Dependencies**: FastAPI, `x9ai.pipeline`, `x9ai.schemas`, `x9ai.config`, `x9ai.logs`, `fastapi.concurrency.run_in_threadpool`, `time`, `json`.
- **Reuses**: components above.
- **Key behaviors**:
  - metadata: absent/empty → `{"language": "pt"}`; invalid JSON → 400 error JSON (SRV-04/06).
  - `audio_file` missing → FastAPI validation error → global handler → 400 (SRV-05).
  - empty file body → 400 (SRV-05); over `max_audio_bytes` → 413 (SRV-07).
  - pipeline runs via `run_in_threadpool` (sync CPU-bound Whisper later); elapsed measured
    with `perf_counter` around the call, `int(round(ms))` (SRV-10).
  - `RequestValidationError` → 400; `Pipeline` exception → 500 + generic + `logger.exception`
    stack in log (SRV-08); anything else → 500 generic.

### `server/tests` — test harness (co-located)

- `conftest.py`: `client` fixture → `TestClient(create_app(pipeline=StubPipeline()))` +
  a `raising_pipeline` fixture for SRV-08.
- `test_contract.py`: SRV-01..04, SRV-10; `test_errors.py`: SRV-05..08; `test_observability.py`: SRV-11.
- **Dependencies**: pytest, httpx (TestClient transport), fastapi.testclient.

---

## Data Models

### HTTP Success — `docs/spec.md` §6.2

```python
@dataclass SuccessResponse: status: "success"; text: str; processing_time_ms: int (>= 0)
```

### HTTP Error

```python
@dataclass ErrorResponse: status: "error"; message: str  # generic, client-safe
```

No persistence anywhere.

---

## Error Handling Strategy

| Error Scenario | Handling | User Impact |
| -------------- | -------- | ----------- |
| `audio_file` missing / multipart malformed | `RequestValidationError` → HTTP 400 error JSON (SRV-05) | Generic message |
| `audio_file` present but zero bytes | handler check → HTTP 400 (SRV-05) | Generic message |
| `metadata` invalid JSON | handler check → HTTP 400 (SRV-06) | Generic message |
| audio > `max_audio_bytes` | HTTP 413 (SRV-07) | Generic message |
| pipeline raises | HTTP 500 generic + `logger.exception` stack server-side (SRV-08) | Generic message |
| unexpected handler exception | HTTP 500 generic | Generic message |

---

## Risks & Concerns

| Concern | Location (file:line) | Impact | Mitigation |
| ------- | -------------------- | ------ | ---------- |
| FastAPI's default 422 body shape differs from our error contract | `app.py` | Client parses `{"detail":...}` → mismatch | Global `RequestValidationError` handler returns exact `ErrorResponse` JSON; tested in `test_errors.py` |
| `python-multipart` absent breaks multipart `File`/`Form` at import | `pyproject.toml` | Server won't boot | Pinned dependency; scaffold task installs and boots smoke test |
| Sync CPU-bound pipeline blocks the event loop | `app.py` | Future Whispers stall concurrent requests | `run_in_threadpool` from day one |
| UploadReadError / huge bodies | `app.py` | Memory pressure | Size bound enforced on read (413); bound env-configurable |
| Timing flakiness in tests | `test_contract.py` | False failures | Assert windows (>= stub sleep, sane upper bound), not exact ms |

---

## Tech Decisions

| Decision | Choice | Rationale |
| -------- | ------ | --------- |
| App construction | `create_app(pipeline=None)` factory | KISS DI; test injection without a container (Approach A) |
| Seam shape | single `Pipeline.process(bytes, lang) -> str` | AD-004 combined interface, never both impls in parallel |
| Default pipeline in this feature | `StubPipeline` | Contract is proven before real NLP exists; `nlp-pipeline` swaps the default |
| Settings | frozen dataclass + `from_env()` | One bound today; no pydantic-settings dependency |
| Test stack | pytest + `fastapi.testclient` + httpx | Official FastAPI testing path, zero extra infra |
| Lint | ruff | Fast, standard, configurable in `pyproject.toml` |

> Project-level decision candidates: none new beyond AD-008..AD-012 already recorded.