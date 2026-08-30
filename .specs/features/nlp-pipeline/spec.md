# nlp-pipeline Specification

## Problem Statement

The X9AI server currently exposes `POST /process` but routes every request through a
deterministic `StubPipeline` (`server/x9ai/pipeline.py`) — no real transcription or
normalization exists. Per `docs/spec.md` §5 and AD-008/AD-011, the server must turn raw
audio into clean, paste-ready PT-BR text through a two-step local pipeline: Whisper
transcription (faster-whisper) followed by a deterministic rule-based normalization pass.
This feature swaps the stub for a real composed pipeline behind the existing `Pipeline`
seam, keeping the stub/fake injectable so deterministic gates run offline.

## Goals

- [ ] A real `Pipeline` implementation composes a transcriber + a rule-based PT-BR normalizer, satisfying `docs/spec.md` §5 (AD-004, AD-008)
- [ ] Transcription uses faster-whisper (AD-011) as a lazy, env-configurable wrapper; deterministic gates use an injected fake transcriber, never a real model
- [ ] Normalization is a deterministic rule-based PT-BR pass removing the §9.2 filler blacklist, capitalizing sentence starts, and ensuring ending punctuation
- [ ] `create_app` uses the real pipeline as its default; the HTTP layer still references only the `Pipeline` seam (no concrete transcriber/normalizer)

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Golden oracle corpus + ≥90% semantic-similarity harness | Feature `golden-oracle` (roadmap #3), consumes this pipeline |
| Real-clip/UAT recording validation | `golden-oracle` scope; needs recording + real model (`docs/spec.md` §9) |
| English normalization rules | §2 fixes PT-BR primary; EN secondary not implemented in v1 |
| Local LLM grammar fixing | AD-008: no local LLM in v1; deterministic rules only |
| Whisper prompting for punctuation/grammar | Normalization is a separate deterministic pass (§5.2) |
| Streaming / partial transcription | §7 explicitly deferred |
| Cloud transcription backend | AD-004: complete swap, never both in parallel |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Default model size | `medium`, env `WHISPER_MODEL` override | Spec §5 targets medium/large; env-config per AD-011 | y |
| faster-whisper dependency | `[whisper]` extra, lazy import | Keeps base env lean; gates run offline; AD-011 engine | y |
| Real model in gates | Not run; fake transcriber injected | No GPU / multi-GB download feasibility; oracle feature owns real validation | y |
| Normalizer scope | Fillers + sentence-start capitalization + ending punctuation (§5.2, §9.2) | AD-008 locked rule-based PT-BR, no LLM | y |
| Filler blacklist | `"tipo","né","então","ééé","um","uh"` | §9.2 exact list | y |
| Empty/whitespace transcription | Normalizer returns empty string; HTTP layer already 400s on empty audio, and empty text is passed through as-is | Non-empty audio can still transcribe to empty; no special-case invented past the contract | n |
| Transcription failure | Propagates as an exception → existing server 500 mapping (SRV-08) | HTTP error mapping established in server-api; no new contract surface | n |
| Model load failure (first call) | Raises → server 500 generic + log | Same as any pipeline failure; server owns diagnostics (§4.1) | n |

**Open questions:** none - all resolved or logged above.

**Implicit-requirement dimensions sweep:** persistence/state N/A (stateless service);
auth/rate limits N/A (single-user localhost, §2); idempotency N/A (client does not retry in
v1, §8); concurrency — transcription is CPU/GPU-bound and runs inside the existing
`run_in_threadpool` seam (established SRV-03/10); observability — the pipeline is invoked
within the already-logged request path (SRV-11); external-dependency failure — model
load/transcribe exceptions map to the documented 500 + generic (SRV-08); state transitions N/A.

---

## User Stories

### P1: Real Composed Pipeline — "Transcribe and clean my recording" ⭐ MVP

**User Story**: As a user, I want my recording transcribed and normalized into clean PT-BR
text, so that I can paste paste-ready output without editing.

**Why P1**: This is the product's core value (`docs/spec.md` §1: "AI is the product"); the
stub exists only to prove the contract.

**Acceptance Criteria**:

1. NLP-01 The server SHALL provide a `Pipeline` implementation that composes a transcriber and a normalizer such that processed audio yields the transcriber's raw text passed through the normalizer.
2. NLP-02 WHEN the real pipeline is constructed with a transcriber and a normalizer THEN the server SHALL return their composed output as clean text from `pipeline.process(audio, language)`.
3. NLP-03 The server SHALL set the real pipeline as the default pipeline used by `create_app`, such that a request with no injected pipeline is served by transcription then normalization.
4. NLP-04 WHEN the transcriber raises any exception THEN the server SHALL let that exception propagate to the HTTP layer, which SHALL respond HTTP 500 with a generic error message and SHALL record the stack server-side (per SRV-08).

**Independent Test**: Build `RealPipeline(FakeTranscriber("o tipo então é bom"), RuleBasedNormalizer())`
and assert `process(b"...", "pt") == "O então é bom."` (transcriber text → normalized);
TestClient with no injected pipeline routes through a real default; inject a raising
transcriber and assert 500 generic + logged stack.

---

### P1: Transcription via faster-whisper — "Transcribe with the local Whisper engine" ⭐ MVP

**User Story**: As a developer, I want the real transcriber to use faster-whisper locally, so
that transcription is private and zero-cost (§5, AD-011).

**Why P1**: AD-011 locks the engine; this story delivers the real (lazy) integration.

**Acceptance Criteria**:

1. NLP-05 The server SHALL expose a `Transcriber` abstraction with a single method that consumes audio bytes and a language and yields raw transcribed text.
2. NLP-06 WHERE the faster-whisper package is present THEN the server SHALL transcribe using faster-whisper with the configured model, device, and compute type.
3. NLP-07 WHERE the faster-whisper package is absent THEN importing the real transcriber module SHALL NOT fail, and only an actual `transcribe` call SHALL raise.
4. NLP-08 The model name, device, and compute type SHALL be configurable via environment variables (`WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`) with `WHISPER_MODEL` defaulting to `medium`.
5. NLP-09 The server SHALL report the selected model name in transcriber configuration so operators can confirm which model is active.

**Independent Test**: With faster-whisper absent, import `x9ai.nlp` and construct the real
transcriber (asserting model/device/compute from env) without exception; assert `transcribe`
on a fake-backed wrapper returns configured values; assert env overrides are read; the
faster-whisper-dependent path is exercised only under the `[whisper]` extra (guarded, not
run in default gates).

---

### P1: Rule-Based PT-BR Normalization — "Remove fillers and fix punctuation" ⭐ MVP

**User Story**: As a user, I want deterministic cleanup of the raw transcript, so that output
needs zero manual editing (§5.2).

**Why P1**: Normalization is half the pipeline and the §9.2 structural proof.

**Acceptance Criteria**:

1. NLP-10 The server SHALL expose a swappable `Normalizer` abstraction with a single method that consumes raw text and yields normalized text.
2. NLP-11 WHEN raw text contains any filler word from the blacklist `"tipo","né","então","ééé","um","uh"` as a case-insensitive whole word THEN the server SHALL remove that filler from the output.
3. NLP-12 WHEN the first word of a sentence has no leading capital THEN the server SHALL capitalize the first character of the sentence.
4. NLP-13 WHEN a sentence does not end with `.`, `!`, or `?` THEN the server SHALL append a `.` to end the sentence.
5. NLP-14 The normalization SHALL be deterministic: the same raw text SHALL always produce the identical normalized output.

**Independent Test**: Feed raw text with all six fillers and assert each is removed;
assert `"o tipo é bom"` → `"O é bom."`; assert mixed casing and missing punctuation are
fixed; assert calling twice yields identical output.

---

## Edge Cases

- IF raw text is only fillers/whitespace THEN normalized output SHALL be empty (NLP-13 applies only where a non-empty sentence remains).
- IF a sentence already ends with ending punctuation THEN no extra `.` is appended (NLP-13).
- IF text already starts capitalized THEN it is left unchanged (NLP-12).
- WHEN a transcriber returns text for language `en` THEN the same normalization rules apply (PT-BR rules treat `"um"`/`"uh"` fillers per §9.2; no separate EN pass in v1).

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| NLP-01 | P1: Real Composed Pipeline | Implemented | Verified |
| NLP-02 | P1: Real Composed Pipeline | Implemented | Verified |
| NLP-03 | P1: Real Composed Pipeline | Implemented | Verified |
| NLP-04 | P1: Real Composed Pipeline | Implemented | Verified |
| NLP-05 | P1: Transcription | Implemented | Verified |
| NLP-06 | P1: Transcription | Implemented | Verified |
| NLP-07 | P1: Transcription | Implemented | Verified |
| NLP-08 | P1: Transcription | Implemented | Verified |
| NLP-09 | P1: Transcription | Implemented | Verified |
| NLP-10 | P1: Normalization | Implemented | Verified |
| NLP-11 | P1: Normalization | Implemented | Verified |
| NLP-12 | P1: Normalization | Implemented | Verified |
| NLP-13 | P1: Normalization | Implemented | Verified |
| NLP-14 | P1: Normalization | Implemented | Verified |

**Coverage:** 14 total, 14 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] `pytest` green: every NLP AC asserted via `RealPipeline` with a fake transcriber and the real normalizer
- [ ] `create_app()` boots and still serves the exact server-api contract (§6) with the real default pipeline
- [ ] Normalization is deterministic and satisfies the §9.2 structural checks (no fillers, capitalized starts, ending punctuation) on representative PT-BR input
- [ ] faster-whisper is lazily imported so the package and `create_app` work without it installed
