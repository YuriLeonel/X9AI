# nlp-pipeline Design

**Spec**: `.specs/features/nlp-pipeline/spec.md`
**Status**: Approved

---

## Architecture Overview

The real `Pipeline` implementation composes two swappable seams — a `Transcriber` and a
`Normalizer` (AD-008) — behind the existing `Pipeline` protocol (AD-004). `create_app`
adopts `RealPipeline(WhisperTranscriber(...), RuleBasedNormalizer())` as its default, so
the HTTP layer still references only the `Pipeline` seam. The real transcriber lazily
imports faster-whisper (AD-011) so the package and `create_app` boot without it; an
injectable model-factory seam lets deterministic gates exercise the transcriber without
downloading a model.

```mermaid
graph TD
    R[POST /process handler] -->|audio bytes + language| P[Pipeline seam]
    P --> Real[RealPipeline]
    Real --> T[Transcriber]
    Real --> N[Normalizer]
    T --> Who[WhisperTranscriber*]
    T --> Fake[FakeTranscriber (tests)]
    N --> RBN[RuleBasedNormalizer]
    P -. stub fallback .-> Stub[StubPipeline]
    Real -->|clean text| R
    *WhisperTranscriber -->|lazy import + model_factory| FW[faster-whisper]
```

**Approach exploration.** Three viable shapes; **Approach A chosen.**

- **A — Flat modules + composed `RealPipeline`** (chosen): `normalizer.py` + `transcriber.py`
  hold the two seams; `RealPipeline` composes them in `pipeline.py`. Matches the existing
  single-file module style (`config`, `logs`, `schemas`); each seam stays importable so the
  `golden-oracle` feature can reuse the real `Normalizer`/`Transcriber` directly.
- **B — `nlp/` subpackage** (`x9ai/nlp/transcriber.py`, `...`): more structure than a
  1-extra-feature server needs; adds a package boundary without code/reuse benefit. Rejected.
- **C — Monolithic `real_pipeline.py`**: fewest files but blurs the `Transcriber`/`Normalizer`
  seams that AD-008 and the oracle explicitly depend on. Rejected.

## Code Reuse Analysis

### Existing Components to Leverage

| Component | Location | How to Use |
| --------- | -------- | ---------- |
| `Pipeline` ABC + `StubPipeline` | `server/x9ai/pipeline.py` | `RealPipeline(Pipeline)` joins the seam; `StubPipeline` remains the fallback/injectable stub |
| `Settings` + `Settings.from_env()` | `server/x9ai/config.py` | Extend with whisper fields; `from_env` reads `WHISPER_MODEL`/`WHISPER_DEVICE`/`WHISPER_COMPUTE_TYPE` |
| `create_app(pipeline=None)` | `server/x9ai/app.py` | Default `pipeline` becomes `RealPipeline(...)`; contract/error mapping untouched |
| `run_in_threadpool` | `server/x9ai/app.py` | Already runs the `Pipeline.process` off the event loop (SRV-03/10) — CPU/GPU-bound transcribe stays blocked-free |

### Integration Points

| System | Integration Method |
| ------ | ----------------- |
| HTTP layer | unchanged — `POST /process` → `Pipeline.process` (SRV-03); real vs fake decided only by `create_app` injection |
| faster-whisper | lazy import inside `WhisperTranscriber.transcribe`; model-factory seam for tests |
| `golden-oracle` (future) | reuses `RuleBasedNormalizer` directly and drives `RealPipeline` with a real transcriber + recorded clips |

---

## Components

### `x9ai/normalizer` — the normalization seam

- **Purpose**: Swappable deterministic text-cleanup pass (AD-008); PT-BR only (§2).
- **Location**: `server/x9ai/normalizer.py`
- **Interfaces**:
  - `class Normalizer(ABC)`: `normalize(text: str) -> str` — abstract.
  - `class RuleBasedNormalizer(Normalizer)`: `FILLERS = ("tipo","né","então","ééé","um","uh")`; deterministic rules:
    1. remove blacklist fillers (case-insensitive whole word),
    2. strip and capitalize first character of the sentence,
    3. append `.` when the sentence does not end in `.`/`!`/`?`.
- **Dependencies**: `re` (Unicode), `abc`. No external packages.
- **Reuses**: none directly; consumed by `RealPipeline` and future oracle.

### `x9ai/transcriber` — the transcription seam

- **Purpose**: Swappable audio→raw-text step (AD-011 engine = faster-whisper); fake-injectable for gates.
- **Location**: `server/x9ai/transcriber.py`
- **Interfaces**:
  - `class Transcriber(ABC)`: `transcribe(audio: bytes, language: str) -> str` — abstract.
  - `class WhisperTranscriber(Transcriber)`: `__init__(settings: Settings | None = None, model_factory: Callable | None = None)`; lazily imports `faster_whisper.WhisperModel` (`from faster_whisper import WhisperModel`) only inside `transcribe`; when `model_factory` is None it builds the lazy default factory; `transcribe` loads the model with `settings.whisper_model/whisper_device/whisper_compute_type`, calls `model.transcribe(BytesIO(audio), language=language)`, joins segment texts, returns stripped raw text.
  - `StubTranscriber(Transcriber)` optional/test helper returning fixed text (not shipped — tests use a FakeTranscriber).
- **Dependencies**: `x9ai.config.Settings`, `io`, `abc`; faster-whisper is a lazy import (extra).
- **Reuses**: `Settings` for model config.

### `x9ai/pipeline` — add the composed real pipeline

- **Purpose**: The real `Pipeline` implementation wiring transcriber → normalizer.
- **Location**: `server/x9ai/pipeline.py` (extend)
- **Interfaces**:
  - `class RealPipeline(Pipeline)`: `__init__(transcriber: Transcriber, normalizer: Normalizer)`; `process(audio, language)` → `normalizer.normalize(transcriber.transcribe(audio, language))`.
- **Dependencies**: `x9ai.transcriber`, `x9ai.normalizer`, existing `Pipeline` ABC.
- **Reuses**: `Pipeline` seam; `StubPipeline` stays for fallback.

### `x9ai/config` — whisper settings

- **Purpose**: Env-configurable Whisper model/device/compute_type (NLP-08).
- **Location**: `server/x9ai/config.py` (extend)
- **Interfaces**: frozen `Settings` gains `whisper_model: str = "medium"`, `whisper_device: str = "auto"`, `whisper_compute_type: str = "default"`; `from_env()` reads `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE` (fallback to defaults on parse/blank).
- **Dependencies**: `os`, `dataclasses`.
- **Reuses**: existing `Settings`/`from_env` pattern.

### `x9ai/app` — adopt the real default

- **Purpose**: Route all real traffic through the composed pipeline.
- **Location**: `server/x9ai/app.py` (modify)
- **Interfaces**: `create_app(pipeline: Pipeline | None = None)` — the `None` default becomes `RealPipeline(WhisperTranscriber(settings), RuleBasedNormalizer())`; HTTP/error/logging code unchanged.
- **Dependencies**: components above; existing FastAPI stack.
- **Reuses**: everything from server-api; no new routes.

### `server/tests` — co-located harness

- `test_normalizer.py`: NLP-10..14 (filler removal, casing, punctuation, determinism, empty/edge).
- `test_transcriber.py`: NLP-05, NLP-07..09 (abstraction, lazy-import-no-fail, config selection, injected model-factory join).
- `test_pipeline.py` (extend): NLP-01..02 (composition with FakeTranscriber + RuleBasedNormalizer), NLP-04 (raising transcriber propagates).
- `test_app.py` / `test_contract.py` (extend): NLP-03 (create_app default routes through real pipeline).

---

## Data Models

No new persistence or request/response data models. The seams are behavioral interfaces
(`transcribe`/`normalize` return `str`). "Data" is the in-memory raw→clean text flow:
`bytes` → (transcriber) → `str` → (normalizer) → `str`.

---

## Error Handling Strategy

| Error Scenario | Handling | User Impact |
| -------------- | -------- | ----------- |
| faster-whisper not installed | `transcribe` raises `ImportError` at call time | HTTP 500 generic (server logs the import error) — only occurs if someone runs the real default without the `[whisper]` extra |
| Model not downloadable / load failure | lazy load raises inside `transcribe` | HTTP 500 generic + server-side stack (SRV-08 path, NLP-04) |
| Transcriber raises any exception | propagated up to `RealPipeline.process` → HTTP layer catches → 500 generic (NLP-04) | Generic message; details in server log |
| Audio decodes to silence/empty transcript | normalizer returns empty string; HTTP layer passes it through | Contract unchanged; no invented special-case |

---

## Risks & Concerns

| Concern | Location (file:line) | Impact | Mitigation |
| ------- | -------------------- | ------ | ---------- |
| faster-whisper import at module level breaks `create_app()` in lean envs | `transcriber.py` | Server won't boot without the extra | Lazy import strictly inside `transcribe` (NLP-07); package import + `create_app()` verified in gates |
| Running real Whisper in gates is infeasible (download, no GPU) | gates | Non-deterministic / heavy | Injectable `model_factory` seam + FakeTranscriber; real path (NLP-06) guarded behind `[whisper]` extra, smoke-tested manually |
| Filler regex over/under-removes valid PT-BR words (e.g. "um") | `normalizer.py` | Wrong output vs §9.2 blacklist | Use Unicode `\b` whole-word, case-insensitive; blacklist pinned to §9.2 exactly; asserted by tests |
| Normalizer appends `.` to already-terminated sentence | `normalizer.py` | Double punctuation | Only append when no `.!?` end (NLP-13), asserted by test |
| Composed pipeline swallows transcriber exceptions | `pipeline.py` | Hides real failure → wrong 200 | `RealPipeline.process` does NOT catch; lets exceptions propagate (NLP-04), asserted by test |
| Whisper device/compute_type invalid string | `config.py` | Faster-whisper fails at load | Config exposes raw strings; failure maps to 500 generic; no special-casing invented |

---

## Tech Decisions

| Decision | Choice | Rationale |
| -------- | ------ | --------- |
| Module layout | flat `normalizer.py` + `transcriber.py` | Matches existing single-file modules; seams stay importable (Approach A) |
| Composition | `RealPipeline(transcriber, normalizer)` in `pipeline.py` | Reuses the existing `Pipeline` seam; no new package boundary |
| Transcriber seam | injectable `model_factory` callable | Deterministic gates without faster-whisper/model download (NLP-06 guarded) |
| faster-whisper dependency | `[whisper]` extra + lazy import | Keeps base env lean; AD-011 engine preserved; NLP-07 |
| Default model | `Settings.whisper_model = "medium"`, env override | Spec §5; AD-011 env-config |
| Normalizer | `RuleBasedNormalizer` implementing `Normalizer` ABC | AD-008 swappable deterministic pass |
| Default pipeline in `create_app` | `RealPipeline(WhisperTranscriber(settings), RuleBasedNormalizer())` | Real behavior by default; stub injectable for contract tests |

> Project-level decisions: none new beyond AD-011 already recorded.
