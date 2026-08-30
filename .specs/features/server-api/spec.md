# server-api Specification

## Problem Statement

The X9AI client sends raw audio to the processing server over a single HTTP boundary.
Without that boundary nothing else works: the client has nothing to call and the NLP
pipeline has nothing to hang on. This feature delivers FastAPI's `POST /process` endpoint
with the exact request/response contract from `docs/spec.md` §6, a sealed error mapping
that keeps details server-side (§4.1), and the pipeline seam that will later host the real
transcription/normalization (AD-004, AD-008). The pipeline is a stub in this feature:
the contract is proven end-to-end with an injected fake before real NLP exists.

## Goals

- [ ] `POST /process` accepts multipart `audio_file` + `metadata` and returns the spec JSON contract (`docs/spec.md` §6)
- [ ] All contract violations and pipeline failures map to generic, client-safe error JSON; details live in server logs (§4.1)
- [ ] Transcription + normalization are reachable only through one swappable pipeline abstraction (AD-004)
- [ ] Server boots via `uvicorn` and contract is proven by TestClient tests with an injected stub pipeline

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Real transcription / normalization | Feature `nlp-pipeline`, swapped in behind the same seam |
| Golden oracle harness | Feature `golden-oracle` |
| Rust client | Feature `client` (consumes this contract) |
| Auth, multi-tenant, streaming | `docs/spec.md` §2, §7, §8 |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| `metadata` absent | Process with default `{"language": "pt"}` | Spec lists the field but §2 fixes PT-BR primary; tolerant default keeps the loop frictionless | n |
| `metadata` not valid JSON | HTTP 400 with generic error JSON | A declared field with a broken value is a contract violation, not a processing failure | n |
| Pipeline exception | HTTP 500 + generic error JSON; full stack logged server-side | Client only needs a friendly message (§4.1); server owns diagnostics | n |
| Max audio size | 50 MB default, `MAX_AUDIO_BYTES` env override → HTTP 413 | Bound guards memory on local Whisper while staying far above realistic clips | n |
| Status code on processing failure vs contract error | Contract violations → 4xx; pipeline failures → 500 status `error` | Clear REST semantics; client parses the JSON body either way | n |
| Empty `audio_file` | HTTP 400 error JSON (not silently accepted) | Empty bytes cannot transcribe; failing fast beats a confusing 500 | n |

**Open questions:** none - all resolved or logged above.

**Implicit-requirement dimensions sweep:** persistence/state N/A (stateless service);
auth/rate limits N/A (single-user localhost, §2); idempotency N/A (client does not retry the
request in v1, §8); concurrency covered by stateless FastAPI handlers; observability via
per-request log line (Req below); external-dependency failure covered by pipeline-exception
mapping; state transitions N/A inside this feature.

---

## User Stories

### P1: Core Contract — "Process my recording and give me clean text" ⭐ MVP

**User Story**: As a user, I want to send a recording and get clean text back, so that I can
move from raw audio straight to paste-ready output.

**Why P1**: This is the product's only HTTP boundary; everything else hangs off it.

**Acceptance Criteria**:

1. SRV-01 The server SHALL expose exactly one HTTP endpoint, method `POST`, path `/process`, accepting `multipart/form-data`.
2. SRV-02 WHEN a request includes a non-empty `audio_file` and valid JSON-in-string `metadata` THEN the server SHALL respond HTTP 200 whose JSON body has `"status":"success"`, a non-empty `"text"`, and a non-negative integer `"processing_time_ms"`.
3. SRV-03 WHEN the request is valid THEN the server SHALL call its pipeline seam with the raw audio bytes and parsed language, and SHALL return the pipeline's clean text verbatim as `"text"`.
4. SRV-04 WHEN `metadata` is absent THEN the server SHALL process the request with language default `"pt"`.

**Independent Test**: Post a small WAV with a stub pipeline; assert the exact 200 JSON shape
and that `text` equals the stub's output; repeat with no `metadata` and observe the default
language reaches the stub.

---

### P1: Error Mapping — "Make failures friendly, keep details server-side" ⭐ MVP

**User Story**: As a user, I want generic, friendly errors, so that a server problem never
leaks internals into my clipboard.

**Why P1**: §4.1 mandates a friendly generic fallback and server-only diagnostics.

**Acceptance Criteria**:

1. SRV-05 IF `audio_file` is missing or empty THEN the server SHALL respond HTTP 400 with a JSON body `{"status":"error","message":"<non-empty generic message>"}`.
2. SRV-06 IF `metadata` is present but not valid JSON THEN the server SHALL respond HTTP 400 with a JSON body `{"status":"error","message":"<non-empty generic message>"}`.
3. SRV-07 IF the audio bytes exceed the configured maximum THEN the server SHALL respond HTTP 413 with a JSON body `{"status":"error","message":"<non-empty generic message>"}`.
4. SRV-08 IF the pipeline seam raises any exception THEN the server SHALL respond HTTP 500 with a JSON body `{"status":"error","message":"<non-empty generic message>"}`, SHALL not echo exception internals in the response, and SHALL record the full exception stack trace in the server log.

**Independent Test**: Drive each failure via TestClient and assert status + `status:"error"`;
inject a raising stub and assert generic message + captured log record.

---

### P1: Pipeline Seam & Observability

**User Story**: As a developer, I want one seam and one measurement, so that swapping
transcription backend and timing behavior never touches the HTTP layer.

**Why P1**: AD-004 (complete swap, never both in parallel) and §6.2 (`processing_time_ms`).

**Acceptance Criteria**:

1. SRV-09 The server SHALL expose a single `Pipeline` abstraction whose single method consumes audio bytes plus language and yields clean text, such that the HTTP layer references no concrete transcriber or normalizer.
2. SRV-10 The server SHALL set `processing_time_ms` to the elapsed wall-clock milliseconds measured across the pipeline call, rounded to an integer.
3. SRV-11 The server SHALL emit one structured log line per handled request containing http method, path, response status, `processing_time_ms`, and the parsed `client_timestamp` if present.

**Independent Test**: Inject a sleeping stub and assert `processing_time_ms` is within the
stub's sleep window; a stub that counts calls proves the seam receives bytes + language.

---

## Edge Cases

- IF `audio_file` missing/empty THEN 400 (+SRV-05)
- IF `metadata` invalid JSON THEN 400 (+SRV-06)
- IF audio > max THEN 413 (+SRV-07)
- IF pipeline raises THEN 500 + generic + stack in log (+SRV-08)
- WHEN `metadata` absent THEN default `"pt"` (+SRV-04)
- IF an unexpected exception occurs before the pipeline (e.g. malformed multipart) THEN 400/500 with generic error JSON, never a raw traceback

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| SRV-01 | P1: Core Contract | Design | Pending |
| SRV-02 | P1: Core Contract | Design | Pending |
| SRV-03 | P1: Core Contract | Design | Pending |
| SRV-04 | P1: Core Contract | Design | Pending |
| SRV-05 | P1: Error Mapping | Design | Pending |
| SRV-06 | P1: Error Mapping | Design | Pending |
| SRV-07 | P1: Error Mapping | Design | Pending |
| SRV-08 | P1: Error Mapping | Design | Pending |
| SRV-09 | P1: Pipeline Seam | Design | Pending |
| SRV-10 | P1: Pipeline Seam | Design | Pending |
| SRV-11 | P1: Pipeline Seam | Design | Pending |

**Coverage:** 11 total, 0 mapped to tasks, 11 unmapped

---

## Success Criteria

- [ ] `pytest` green: every SRV AC asserted via TestClient against injected stubs
- [ ] `uvicorn x9ai.app:app` boots; a `curl -F` multipart call returns the documented success JSON verbatim
- [ ] Contract is deterministic: same stub pipeline + same input → same response (no LLM in the loop)