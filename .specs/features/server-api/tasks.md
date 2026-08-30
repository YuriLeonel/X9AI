# server-api Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/server-api/design.md`
**Status**: Approved

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: `AGENTS.md` (no concrete test-type mandates; stack/gate expectations defaulted). Branch strategy AD-012.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Pipeline seam (`pipeline.py`) | unit | All branches; 1:1 to SRV-09; stub determinism pinned | `server/tests/test_pipeline.py` | `pytest` |
| Schemas (`schemas.py`) | unit | Success/error JSON serialization shape; negative ms rejected | `server/tests/test_schemas.py` | `pytest` |
| Config (`config.py`) | unit | Env override + defaults; malformed env value handling | `server/tests/test_config.py` | `pytest` |
| App route (`app.py`) | integration | The 1 in-scope route: happy + every listed edge case (SRV-01..08, SRV-10) | `server/tests/test_contract.py`, `test_errors.py` | `pytest` |
| Observability (`logs.py`) | integration | Request log line asserts method/path/status/timing/timestamp (SRV-11) | `server/tests/test_logging.py` | `pytest` |
| Scaffold (`pyproject.toml`, `__init__.py`) | none | Build gate only (import smoke) | `server/tests/test_scaffold.py` | Build gate |

## Gate Check Commands

> Generated from codebase - confirm before Execute. All commands run from `server/` with `.venv`.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After unit-only tasks | `.venv/bin/python -m pytest -q` |
| Full | After route/integration tasks | `.venv/bin/python -m pytest && .venv/bin/ruff check .` |
| Build | Scaffold/config tasks + pre-merge | `.venv/bin/python -m pytest && .venv/bin/ruff check . && .venv/bin/python -c "from x9ai.app import create_app; a = create_app(); assert '/process' in a.openapi()['paths']"` |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Foundation

Package + the seam's three building blocks.

```
Phase 1:  T1, T2, T3, T4   (T2, T3, T4 each depend on T1)
Phase 2:  T5               (depends on T2, T3, T4)
Phase 3:  T6, T7           (each depends on T5)
```

### Phase 2: Contract

The happy-path endpoint proving the spec §6 shape.

```
T5
```

### Phase 3: Errors & Observability

Failure mapping and per-request logging.

```
T6  (depends on T5)
T7  (depends on T5)
```

---

## Task Breakdown

### T1: Scaffold Python package and toolchain

**What**: `server/pyproject.toml` with setuptools metadata, pinned deps (`fastapi`, `uvicorn[standard]`, `python-multipart`), dev deps (`pytest`, `httpx`, `ruff`), pytest + ruff config; `server/x9ai/__init__.py`; `server/tests/test_scaffold.py` import smoke; create `server/.venv` and install.
**Where**: `server/pyproject.toml`
**Depends on**: None
**Reuses**: none
**Requirement**: SRV-01 (foundation)

**Tools**:

- MCP: no MCP servers available
- Skill: NONE

**Done when**:

- [ ] `import x9ai` succeeds inside `.venv`
- [ ] `pytest` collects and passes `tests/test_scaffold.py` (no exit code 5)
- [ ] Build gate passes: `pytest -q && ruff check .`
- [ ] Test count: 1 test / 1 assertion (no silent deletions)

**Tests**: none (scaffold; build gate only)
**Gate**: build
**Commit**: `chore(server): scaffold python package and toolchain`

---

### T2: Add pipeline seam and stub implementation

**What**: `server/x9ai/pipeline.py`: abstract `Pipeline` (AD-004 single combined interface) with `process(audio: bytes, language: str) -> str`, and deterministic `StubPipeline` returning `stub:<language>:<len(audio)>`.
**Where**: `server/x9ai/pipeline.py`
**Depends on**: T1
**Reuses**: none
**Requirement**: SRV-09

**Tools**:

- MCP: no MCP servers available
- Skill: NONE

**Done when**:

- [ ] `Pipeline` is abstract; instantiating it raises `TypeError`
- [ ] `StubPipeline.process` returns the pinned deterministic string and derives both args (bytes length + language) so seam receives both
- [ ] Tests assert call-arg propagation and determinism
- [ ] Quick gate passes: `pytest -q`; Test count: 3 tests (no silent deletions)

**Tests**: unit
**Gate**: quick
**Commit**: `feat(server): add pipeline seam with stub implementation`

---

### T3: Add success and error response schemas

**What**: `server/x9ai/schemas.py`: Pydantic `SuccessResponse` (`status: "success"`, `text: str`, `processing_time_ms: int >= 0` via `Field(ge=0)`); `ErrorResponse` (`status: "error"`, `message: str`).
**Where**: `server/x9ai/schemas.py`
**Depends on**: T1
**Reuses**: pydantic v2
**Requirement**: SRV-02

**Tools**:

- MCP: no MCP servers available
- Skill: NONE

**Done when**:

- [ ] Both models serialize to the exact §6.2 JSON shape
- [ ] `processing_time_ms` negative rejected by validation
- [ ] `status` `Literal` rejects wrong values
- [ ] Quick gate passes: `pytest -q`; Test count: 4 tests (no silent deletions)

**Tests**: unit
**Gate**: quick
**Commit**: `feat(server): add success and error response schemas`

---

### T4: Add env-configurable settings

**What**: `server/x9ai/config.py`: frozen dataclass `Settings(max_audio_bytes: int = 52_428_800)` + `Settings.from_env()` reading `MAX_AUDIO_BYTES`; invalid/malformed env value falls back to default.
**Where**: `server/x9ai/config.py`
**Depends on**: T1
**Reuses**: none
**Requirement**: SRV-07

**Tools**:

- MCP: no MCP servers available
- Skill: NONE

**Done when**:

- [ ] Default is 50 MiB
- [ ] Env override honored (monkeypatched `MAX_AUDIO_BYTES`)
- [ ] Malformed env value → default, no crash
- [ ] Quick gate passes: `pytest -q`; Test count: 3 tests (no silent deletions)

**Tests**: unit
**Gate**: quick
**Commit**: `feat(server): add env-configurable settings`

---

### T5: Handle POST /process happy path with timing

**What**: `server/x9ai/app.py` + `server/tests/conftest.py` (`client` fixture via `TestClient(create_app(pipeline=StubPipeline()))`): `create_app(pipeline=None)` defaulting to `StubPipeline`; `POST /process` accepting `audio_file: UploadFile` + `metadata: str | None`; metadata absent/empty → `{"language": "pt"}`; `run_in_threadpool(pipeline.process, ...)`; `perf_counter` timing → `int(round(ms))`; success → `SuccessResponse` JSON.
**Where**: `server/x9ai/app.py`
**Depends on**: T2, T3, T4
**Reuses**: components T2-T4
**Requirement**: SRV-01, SRV-02, SRV-03, SRV-04, SRV-10

**Tools**:

- MCP: no MCP servers available
- Skill: NONE

**Done when**:

- [ ] Route is `POST /process`, `multipart/form-data`, and the only route in the app (SRV-01)
- [ ] Valid request → 200 `{"status":"success","text":"...","processing_time_ms":>=0}` (SRV-02)
- [ ] `text` equals the stub's stdout: `stub:pt:<len>`; stub receives bytes + language (SRV-03)
- [ ] No `metadata` → language `pt` reaches stub (SRV-04)
- [ ] `processing_time_ms` in the stub's sleep window via a sleeping stub (SRV-10)
- [ ] Full gate passes: `pytest && ruff check .`
- [ ] Test count: 5+ tests (no silent deletions)

**Tests**: integration
**Gate**: full
**Commit**: `feat(server): handle POST /process happy path with timing`

---

### T6: Map contract violations and pipeline errors

**What**: `server/x9ai/app.py` (modify): global `RequestValidationError` handler → 400 error JSON; empty `audio_file` → 400; invalid JSON `metadata` → 400; audio over `max_audio_bytes` → 413; pipeline exception → 500 generic + `logger.exception` stack server-side; unexpected handler exception → 500 generic. Uses `ErrorResponse` everywhere.
**Where**: `server/x9ai/app.py`
**Depends on**: T5
**Reuses**: schemas + config from T3/T4
**Requirement**: SRV-05, SRV-06, SRV-07, SRV-08

**Tools**:

- MCP: no MCP servers available
- Skill: NONE

**Done when**:

- [ ] Missing/empty `audio_file` → 400 with `{"status":"error","message":...}` (SRV-05)
- [ ] Invalid `metadata` JSON → 400 error JSON (SRV-06)
- [ ] Oversized audio → 413 error JSON (SRV-07)
- [ ] Raising stub pipeline → 500 generic message that does NOT echo the exception text; `caplog` proves full stack trace logged (SRV-08)
- [ ] Response never returns raw traceback/detail arrays
- [ ] Full gate passes: `pytest && ruff check .`
- [ ] Test count: 8+ tests (no silent deletions)

**Tests**: integration
**Gate**: full
**Commit**: `feat(server): map contract violations and pipeline errors`

---

### T7: Emit structured per-request log line

**What**: `server/x9ai/logs.py` (`configure_logging()` + `log_request(...)` emitting `method= path= status= processing_time_ms= client_timestamp=`); wire one call per handled request in `app.py` (both success and error paths).
**Where**: `server/x9ai/logs.py`
**Depends on**: T5
**Reuses**: components T3-T6
**Requirement**: SRV-11

**Tools**:

- MCP: no MCP servers available
- Skill: NONE

**Done when**:

- [ ] One log line per request on success and on every error path
- [ ] Line contains method, path, status, `processing_time_ms`
- [ ] `client_timestamp` present in the line when supplied in metadata, absent when not
- [ ] Full gate passes: `pytest && ruff check .`
- [ ] Test count: 4 tests (no silent deletions)

**Tests**: integration
**Gate**: full
**Commit**: `feat(server): emit structured per-request log line`

---

## Phase Execution Map

Visual representation of task ordering. Phases run in sequence, and tasks within a phase run in order:

```
Phase 1 ---------→ Phase 2 ---------→ Phase 3

T1 → T2
T1 → T3
T1 → T4
T2 → T5
T3 → T5
T4 → T5
T5 → T6
T5 → T7
```

Execution is strictly sequential - there is no intra-phase parallelism.

---

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: scaffold package + toolchain | 1 manifest + package init | ✅ Granular |
| T2: pipeline seam | 1 file / 1 concern | ✅ Granular |
| T3: response schemas | 1 file / 1 concern | ✅ Granular |
| T4: settings | 1 file / 1 concern | ✅ Granular |
| T5: happy-path endpoint | 1 route / 1 file | ✅ Granular |
| T6: error mapping | 1 file (modify) / 1 concern | ✅ Granular |
| T7: request logging | 1 file + wiring / 1 concern | ✅ Granular |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | root | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T1 | T1 → T3 | ✅ Match |
| T4 | T1 | T1 → T4 | ✅ Match |
| T5 | T2, T3, T4 | T2/T3/T4 → T5 | ✅ Match |
| T6 | T5 | T5 → T6 | ✅ Match |
| T7 | T5 | T5 → T7 | ✅ Match |

No dependency points forward to a later phase.

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | -------------------------- | --------------- | --------- | ------ |
| T1: scaffold | Scaffold/config | none (build gate) | none | ✅ OK |
| T2: pipeline seam | Pipeline seam | unit | unit | ✅ OK |
| T3: schemas | Schemas | unit | unit | ✅ OK |
| T4: settings | Config | unit | unit | ✅ OK |
| T5: happy path | App route | integration | integration | ✅ OK |
| T6: error mapping | App route | integration | integration | ✅ OK |
| T7: logging | Observability | integration | integration | ✅ OK |