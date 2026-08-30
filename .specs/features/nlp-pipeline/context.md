# nlp-pipeline Context

**Gathered:** 2026-08-30
**Spec:** `.specs/features/nlp-pipeline/spec.md`
**Status:** Ready for design

---

## Feature Boundary

Implement the real transcription + normalization pipeline behind the existing `Pipeline`
seam (`docs/spec.md` §5), and make it the default pipeline consumed by `create_app`.
Delivery keeps the stub/fake injectable so all deterministic gates run offline without a
multi-GB Whisper model. The golden oracle (feature `golden-oracle`) comes later.

---

## Implementation Decisions

### Transcription engine

- Faster-whisper (CTranslate2) — locked by AD-011. Local, privacy-preserving, PT-BR
  proficient. No cloud in v1.
- Default model size **`medium`**, env-overridable (`WHISPER_MODEL`). Supports the
  medium/large tiers the spec §5 targets while staying practical on local hardware.
  Device/compute-type also env-overridable (`WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`).
- The faster-whisper import and model load are **lazy** (first `transcribe` call), so
  the module imports and `create_app()` boots even where faster-whisper is not installed.
- faster-whisper is a **`[whisper]` extra dependency**, not a hard dependency — keeps the
  base dev/CI environment lean (no forced torch download).

### Deliverable vs deterministic gates

- Implement the real `WhisperTranscriber` calling faster-whisper, but gates run with an
  **injectable fake transcriber** (fixed deterministic text) plus the real rule-based
  normalizer. Real-model smoke testing is deferred to manual verification after this branch.
- The `Pipeline` consumer (HTTP layer) never references concrete transcriber/normalizer —
  only the seam (AD-004). Wiring happens in `create_app`'s default pipeline.

### Normalizer

- Deterministic, rule-based PT-BR only, behind a swappable `Normalizer` interface
  (AD-008). No local LLM in v1.
- Scope: filler removal + sentence-start capitalization + ending punctuation, matching
  `docs/spec.md` §5.2 and §9.2 exactly.
- Filler blacklist: `"tipo"`, `"né"`, `"então"`, `"ééé"`, `"um"`, `"uh"` (word-boundary,
  case-insensitive where sensible).

### Pipeline composition

- One `RealPipeline` composed of `Transcriber` + `Normalizer`, implementing the `Pipeline`
  seam. `create_app` defaults to `RealPipeline(WhisperTranscriber(...), RuleBasedNormalizer())`.

### Agent's Discretion

- Exact filler-region regex form (case-insensitive word boundary vs. exact tokens) within
  the `"tipo"/"né"/"então"/"ééé"/"um"/"uh"` blacklist.
- Exact rule ordering (fillers first, then casing, then punctuation) — normalization is
  bundled and asserted as one deterministic output.
- Faster-whisper invocation specifics (segment join, language hint) inside the lazy wrapper.

### Declined / Undiscussed Gray Areas → Assumptions

- Real-model accuracy/recording validation belongs to `golden-oracle`; not assessed here
  (moves to spec Assumptions).
- English secondary normalization not implemented in v1 (PT-BR rules only) — per §2 fallback.

---

## Specific References

- `docs/spec.md` §5 (NLP pipeline), §5.2 (normalization pass), §9.2 (filler blacklist).
- `server/x9ai/pipeline.py`: `Pipeline` ABC + `StubPipeline` (the seam this implements).
- `server/x9ai/app.py`: `create_app(pipeline=None)` — the wiring point.

---

## Deferred Ideas

None - discussion stayed within feature scope.
