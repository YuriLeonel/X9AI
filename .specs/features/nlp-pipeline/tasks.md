# nlp-pipeline Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/nlp-pipeline/design.md`
**Status**: Approved

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: `AGENTS.md` (no concrete test-type mandates; stack/gate expectations defaulted). Branch strategy AD-012. faster-whisper is a lazy `[whisper]` extra — gates run WITHOUT it installed; transcriber tests inject a `model_factory`/FakeTranscriber.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Config (`config.py`) | unit | Env overrides + defaults + malformed value handling (NLP-08) | `server/tests/test_config.py` | `pytest` |
| Normalizer (`normalizer.py`) | unit | 1:1 to NLP-10..14: filler removal all blacklist, casing, punctuation, determinism, empty/fillers-only edge | `server/tests/test_normalizer.py` | `pytest` |
| Transcriber (`transcriber.py`) | unit | NLP-05..09: abstraction, lazy-import-no-fail, config selection, model report, injected model-factory join | `server/tests/test_transcriber.py` | `pytest` |
| Pipeline (`pipeline.py`) | unit | NLP-01..02 composition, NLP-04 exception propagation | `server/tests/test_pipeline.py` | `pytest` |
| App route (`app.py`) | integration | NLP-03: `create_app()` default routes through the real pipeline (contract §6 preserved) | `server/tests/test_contract.py` | `pytest` |

## Gate Check Commands

> Generated from codebase - confirm before Execute. All commands run from `server/` with `.venv`.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After unit-only tasks | `.venv/bin/python -m pytest -q` |
| Full | After integration tasks | `.venv/bin/python -m pytest && .venv/bin/ruff check .` |
| Build | Phase completion / wiring tasks | `.venv/bin/python -m pytest && .venv/bin/ruff check . && .venv/bin/python -c "from x9ai.app import create_app; from x9ai.pipeline import RealPipeline; a = create_app(); assert isinstance(a, object)"` |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Foundation

The two seams + config foundation. T1 and T2 are independent; T3 depends on T1.

```
Phase 1:  T1, T2, T3   (T3 depends on T1)
Phase 2:  T4           (depends on T2, T3)
Phase 3:  T5           (depends on T4)
```

### Phase 2: Composition

`RealPipeline` wiring transcriber → normalizer.

```
T4
```

### Phase 3: Integration

`create_app` adopts the real pipeline as its default.

```
T5
```

---

## Task Breakdown

### T1: Add whisper settings to config

**What**: Extend `server/x9ai/config.py` frozen `Settings` with `whisper_model: str = "medium"`, `whisper_device: str = "auto"`, `whisper_compute_type: str = "default"`; `Settings.from_env()` reads `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`, falling back to defaults on blank/missing.
**Where**: `server/x9ai/config.py`
**Depends on**: None
**Reuses**: existing `Settings`/`from_env` pattern
**Requirement**: NLP-08

**Tools**:

- MCP: no MCP servers available
- Skill: NONE

**Done when**:

- [ ] Defaults are `medium`/`auto`/`default`
- [ ] Env overrides honored via `from_env` (monkeypatched env vars)
- [ ] Malformed/blank env values fall back to defaults without crashing
- [ ] Quick gate passes: `.venv/bin/python -m pytest -q`; Test count: 4 tests (no silent deletions)

**Tests**: unit
**Gate**: quick
**Commit**: `feat(server): add whisper settings to config`
**Status**: ✅ Complete

---

### T2: Add rule-based PT-BR normalizer

**What**: `server/x9ai/normalizer.py`: abstract `Normalizer` with `normalize(text: str) -> str`; `RuleBasedNormalizer` with `FILLERS = ("tipo","né","então","ééé","um","uh")` removing fillers (Unicode whole-word, case-insensitive), collapsing whitespace, capitalizing the first character of the sentence, and appending `.` when the text does not end in `.`/`!`/`?`.
**Where**: `server/x9ai/normalizer.py`
**Depends on**: None
**Reuses**: none
**Requirement**: NLP-10, NLP-11, NLP-12, NLP-13, NLP-14

**Tools**:

- MCP: no MCP servers available
- Skill: NONE

**Done when**:

- [ ] `Normalizer` is abstract; instantiating raises TypeError
- [ ] Each of the six fillers removed as case-insensitive whole words (NLP-11)
- [ ] Lowercase sentence start capitalized (NLP-12)
- [ ] Missing ending punctuation gets `.`; already-terminated sentences unchanged (NLP-13)
- [ ] Deterministic: same input → same output across calls (NLP-14)
- [ ] Fillers-only / whitespace input → empty output; internal space collapsed
- [ ] Quick gate passes: `.venv/bin/python -m pytest -q`; Test count: 8 tests (no silent deletions)

**Tests**: unit
**Gate**: quick
**Commit**: `feat(server): add rule-based pt-br normalizer`

---

### T3: Add lazy faster-whisper transcriber

**What**: `server/x9ai/transcriber.py`: abstract `Transcriber` with `transcribe(audio: bytes, language: str) -> str`; `WhisperTranscriber(settings=None, model_factory=None)` that lazily imports `faster_whisper.WhisperModel` ONLY inside `transcribe` (default factory), loads with `settings.whisper_model/device/compute_type`, calls `model.transcribe(BytesIO(audio), language=language)`, and joins segment texts into stripped raw text. Add `[whisper] faster-whisper` extra to `server/pyproject.toml`.
**Where**: `server/x9ai/transcriber.py`, `server/pyproject.toml`
**Depends on**: T1
**Reuses**: `Settings` from T1
**Requirement**: NLP-05, NLP-06, NLP-07, NLP-08, NLP-09

**Tools**:

- MCP: no MCP servers available
- Skill: NONE

**Done when**:

- [ ] `Transcriber` abstract; instantiation raises TypeError (NLP-05)
- [ ] Importing `x9ai.transcriber` and constructing `WhisperTranscriber` succeed WITHOUT faster-whisper installed; only `transcribe` with the default factory raises (NLP-07)
- [ ] A supplied `model_factory` is invoked with the configured model/device/compute_type and its segment output is joined into the returned raw text (NLP-06-guarded, NLP-09)
- [ ] Env/`Settings` values selected (model defaults to `medium`) (NLP-08)
- [ ] Quick gate passes: `.venv/bin/python -m pytest -q`; Test count: 7 tests (no silent deletions)

**Tests**: unit
**Gate**: quick
**Commit**: `feat(server): add lazy faster-whisper transcriber`

---

### T4: Add composed RealPipeline

**What**: Extend `server/x9ai/pipeline.py` with `RealPipeline(Pipeline)` holding `transcriber: Transcriber` + `normalizer: Normalizer`; `process(audio, language)` returns `normalizer.normalize(transcriber.transcribe(audio, language))` WITHOUT catching transcriber exceptions.
**Where**: `server/x9ai/pipeline.py`
**Depends on**: T2, T3
**Reuses**: `Transcriber` (T3), `Normalizer` (T2), `Pipeline` ABC
**Requirement**: NLP-01, NLP-02, NLP-04

**Tools**:

- MCP: no MCP servers available
- Skill: NONE

**Done when**:

- [ ] `RealPipeline` implements the `Pipeline` interface (NLP-01)
- [ ] `process(audio, language)` returns normalizer output applied to transcriber output (NLP-02)
- [ ] A raising transcriber's exception propagates out of `process` uncaught (NLP-04)
- [ ] Quick gate passes: `.venv/bin/python -m pytest -q`; Test count: 4 tests (no silent deletions)

**Tests**: unit
**Gate**: quick
**Commit**: `feat(server): add composed real pipeline`

---

### T5: Adopt real pipeline as create_app default

**What**: Modify `server/x9ai/app.py` `create_app(pipeline=None)`: the `None` default builds `RealPipeline(WhisperTranscriber(settings), RuleBasedNormalizer())`; HTTP/error/logging unchanged. Assert `create_app()` boots without faster-whisper and that, when a transcriber is injected through a real `RealPipeline`, `POST /process` returns the normalized text end-to-end (test injects a fake transcriber via a configured pipeline).
**Where**: `server/x9ai/app.py`
**Depends on**: T4
**Reuses**: components T1-T4
**Requirement**: NLP-03

**Tools**:

- MCP: no MCP servers available
- Skill: NONE

**Done when**:

- [ ] `create_app()` with no arg constructs the real default (RealPipeline + WhisperTranscriber + RuleBasedNormalizer) without importing faster-whisper (NLP-03, NLP-07)
- [ ] `POST /process` via TestClient through a `RealPipeline(FakeTranscriber, RuleBasedNormalizer)` returns 200 success with normalized `text` (NLP-03 end-to-end)
- [ ] Existing contract tests still pass unchanged (§6 preserved)
- [ ] Full gate passes: `.venv/bin/python -m pytest && .venv/bin/ruff check .`; Test count: 3+ new tests (no silent deletions)

**Tests**: integration
**Gate**: full
**Commit**: `feat(server): adopt real pipeline as create_app default`

---

## Phase Execution Map

Visual representation of task ordering. Phases run in sequence, and tasks within a phase run in order:

```
Phase 1 ---------→ Phase 2 ---------→ Phase 3

T1 → T3
T2 → T4
T3 → T4
T4 → T5
```

Execution is strictly sequential - there is no intra-phase parallelism.

---

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: whisper config settings | 1 file / 1 concern | ✅ Granular |
| T2: rule-based normalizer | 1 file / 1 concern | ✅ Granular |
| T3: transcriber + pyproject extra | 2 files / 1 concern (same feature subsystem) | ✅ Granular |
| T4: composed RealPipeline | 1 file (extend) / 1 concern | ✅ Granular |
| T5: create_app default | 1 file (modify) / 1 concern | ✅ Granular |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | root | ✅ Match |
| T2 | None | root | ✅ Match |
| T3 | T1 | T1 → T3 | ✅ Match |
| T4 | T2, T3 | T2/T3 → T4 | ✅ Match |
| T5 | T4 | T4 → T5 | ✅ Match |

No dependency points forward to a later phase.

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1: whisper config | Config | unit | unit | ✅ OK |
| T2: normalizer | Normalizer | unit | unit | ✅ OK |
| T3: transcriber | Transcriber | unit | unit | ✅ OK |
| T4: RealPipeline | Pipeline | unit | unit | ✅ OK |
| T5: create_app default | App route | integration | integration | ✅ OK |
