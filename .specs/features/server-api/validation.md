# server-api Validation

**Date**: 2026-08-30
**Spec**: `.specs/features/server-api/spec.md`
**Diff range**: `main..feature/server-api` (base `db893cf`, 7 commits)
**Verifier**: independent sub-agent (author ≠ verifier)

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 | ✅ Done | Scaffold + pyproject + import smoke pass |
| T2 | ✅ Done | Pipeline seam + StubPipeline tests pass |
| T3 | ✅ Done | Success/Error schema tests pass |
| T4 | ✅ Done | Settings env-override tests pass |
| T5 | ✅ Done | Happy-path endpoint + timing tests pass |
| T6 | ✅ Done | Error mapping tests pass |
| T7 | ✅ Done | Request logging tests pass |

All 7 tasks marked `✅ Complete` in `.specs/features/server-api/tasks.md` (lines 99, 126, 153, 180, 210, 240, 268); no blocked or partial tasks.

---

## Spec-Anchored Acceptance Criteria

| Criterion (WHEN X THEN Y) | Spec-defined outcome | `file:line` + assertion | Result |
| ------------------------- | -------------------- | ----------------------- | ------ |
| SRV-01 expose exactly one endpoint, `POST /process`, multipart | exactly one `APIRoute`, path `/process`, method `POST` only | `server/tests/test_contract.py:13` - `assert [(r.path, sorted(r.methods)) for r in custom] == [("/process", ["POST"])]`; Build-gate route assert (same expression) | ✅ PASS |
| SRV-02 valid request → 200 `{"status":"success","text":<non-empty>,"processing_time_ms":<non-neg int>}` | 200; `status:"success"`; non-empty text; `processing_time_ms` int ≥ 0 | `server/tests/test_contract.py:22-27` - `assert response.status_code == 200`; `body["status"] == "success"`; `body["text"] == "stub:pt:3"` (non-empty); `isinstance(body["processing_time_ms"], int)`; `body["processing_time_ms"] >= 0`. Schema-level: `server/tests/test_schemas.py:9-15` (exact §6.2 shape), `:18-20` (negative rejected), `:23-25` (wrong status rejected) | ✅ PASS |
| SRV-03 valid request → pipeline called with raw bytes + parsed language; `text` returned verbatim | `text` equals pipeline output; stub derives bytes len + language | `server/tests/test_contract.py:25` - `body["text"] == "stub:pt:3"` (bytes=3); `:54` - `response.json()["text"] == "stub:en:4"` (language forwarded). Seam unit: `server/tests/test_pipeline.py:14` - `result == "stub:pt:3"`; `:20` determinism | ✅ PASS |
| SRV-04 metadata absent → language default `"pt"` | pipeline receives `"pt"` | `server/tests/test_contract.py:36` - `response.json()["text"] == "stub:pt:4"`; empty `{}` also defaults: `:45` - `response.json()["text"] == "stub:pt:4"` | ✅ PASS |
| SRV-05 missing/empty `audio_file` → 400 error JSON | 400; `{"status":"error","message":<non-empty generic>}` | `server/tests/test_errors.py:14-15` - `assert response.status_code == 400`; `response.json() == {"status":"error","message":"invalid request"}` (missing); `:23-25` - 400 + `["status"] == "error"` + truthy `message` (empty bytes) | ✅ PASS |
| SRV-06 `metadata` present but not valid JSON → 400 error JSON | 400; `status:"error"` | `server/tests/test_errors.py:34-35` - 400 + status `"error"` (malformed `{nope`); `:44-45` - 400 + status `"error"` (non-object `[]`) | ✅ PASS |
| SRV-07 audio > configured max → 413 error JSON | 413; `status:"error"`; bound env-configurable, default 50 MiB | `server/tests/test_errors.py:54-55` - `assert response.status_code == 413`; `response.json()["status"] == "error"` (Settings(max_audio_bytes=2), 5-byte file). Config: `server/tests/test_config.py:11` - `== 50 * 1024 * 1024`; `:16` env override; `:21`/`:26` fallback | ✅ PASS |
| SRV-08 pipeline raises → 500 error JSON, no internals echoed, stack in server log | 500; `{"status":"error","message":<non-empty generic>}`; exception text NOT in body; traceback in log | `server/tests/test_errors.py:64-68` - `assert response.status_code == 500`; `body == {"status":"error","message":"processing failed"}`; `"boom-internal-detail" not in body["message"]`; `"boom-internal-detail" in caplog.text` | ✅ PASS |
| SRV-09 single `Pipeline` seam: process(bytes, language) → str; HTTP layer references no concrete transcriber | `Pipeline` abstract; instantiation raises `TypeError`; stub consumes both args | `server/tests/test_pipeline.py:9` - `with pytest.raises(TypeError): Pipeline()`; `:14` - stub derives `language` + `len(audio)`; HTTP layer injects seam: `server/tests/conftest.py:19` - `TestClient(create_app(pipeline=StubPipeline()))` | ✅ PASS |
| SRV-10 `processing_time_ms` = elapsed wall-clock ms across pipeline call, rounded int | int ≥ stub sleep window, sane upper bound | `server/tests/test_contract.py:70-71` - `assert body["processing_time_ms"] >= 40` (0.05 s sleep); `body["processing_time_ms"] <= wall_ms + 2`; `:26` `isinstance(..., int)` | ✅ PASS |
| SRV-11 one structured log line per request: method, path, status, `processing_time_ms`, `client_timestamp` if present | single line; fields present; timestamp included iff supplied | `server/tests/test_logging.py:30` - `assert len(lines) == 1`; `:33-36` - `method=="POST"`, `path=="/process"`, `status==200`, int `processing_time_ms`; `:37` - `client_timestamp == 1715000000`; `:47` - `"client_timestamp" not in line` when absent; `:53` 400 logged; `:62` 500 logged | ✅ PASS |

**Status**: ✅ 11/11 ACs covered, asserted values match spec-defined outcomes. **0 spec-precision gaps.**

Note on error `message` strings: `docs/spec.md` §6.2 and §4.1 define the error body shape (`status:"error"`, `"<generic error string mapped by the server>"`) but deliberately leave the message content to the server; tests pin the server-chosen generic strings (`"invalid request"`, `"processing failed"`) which satisfy the spec constraint, so this is not a gap.

---

## Discrimination Sensor

| Mutation | File:line | Description | Killed? |
| -------- | --------- | ----------- | ------- |
| 1 | `server/x9ai/app.py:76` | Success status value `"success"` → `"ok"` in `SuccessResponse(...)` | ✅ Killed (`tests/test_contract.py::test_valid_request_returns_success_contract` failed; schema rejects wrong status → success path breaks) |
| 2 | `server/x9ai/app.py:71` | Removed `logger.exception("pipeline processing failed")` in pipeline-exception branch | ✅ Killed (`tests/test_errors.py::test_pipeline_failure_returns_500_generic_and_logs_stack` failed; stack no longer reaches log) |
| 3 | `server/x9ai/app.py:56` | Flipped `if not audio:` → `if audio:` (empty-audio guard) | ✅ Killed (`tests/test_errors.py::test_empty_audio_file_returns_400_with_error_contract` failed; empty file no longer 400) |

**Sensor depth**: lightweight (3 targeted mutations; highest-risk logic = SRV-08 error mapping, SRV-10 timing + SRV-03 text propagation)
**Result**: 3/3 killed - ✅ PASS

Sensor ran in isolated scratch `/tmp/opencode/x9ai-sensor-server` (copy of `server/`, venv python reused via `PYTHONPATH`). Scratch-source resolution was proven with a sentinel print before injecting faults (sentinel appeared in test output). Scratch discarded with `rm -rf`; real worktree porcelain re-verified exact baseline (empty) after cleanup.

---

## Interactive UAT Results (if performed)

Not performed: backend-only HTTP feature, no user-facing surface. Automated checks suffice (validate.md step 3).

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ 120-line app, 16-26-line modules; no dead code |
| Surgical changes | ✅ Diff surface = server tree + `.specs/` only; greenfield |
| No scope creep | ✅ No auth/streaming/DB; scope matches spec.md Out of Scope |
| Matches patterns | ✅ Ruff clean (line-length 100); module docstrings; spec refs (`docs/spec.md §6`) |
| Spec-anchored outcome check (asserted values match spec) | ✅ 11/11 |
| Per-layer Coverage Expectation met (domain 1:1 ACs; routes happy+edge+error) | ✅ Domain: pipeline seam SRV-09, schemas SRV-02, config SRV-07 all 1:1 (tasks.md matrix lines 22-24). Routes: happy + missing/empty audio + invalid JSON + non-object + oversized + pipeline exception (tasks.md line 25) |
| Every test maps to a spec requirement - no unclaimed tests | ✅ All 31 tests traced to SRV-01..11 or Build-gate scaffold |
| Documented guidelines followed: `AGENTS.md` (spec-driven, single `POST /process` boundary, §6 contract, atomic Conventional Commits per task - 7 commits match T1-T7) | ✅ |

Senior-review note: `x9ai/app.py:45-46` `_status_of` defaults non-JSONResponse to 200; acceptable for the `SuccessResponse` model return. Generic 500 handler (`app.py:97-101`) is not directly exercised by any test - minor strengthening opportunity, not a scope-required path (see Edge Cases).

---

## Edge Cases

- [x] `audio_file` missing/empty → 400: `tests/test_errors.py:14-15`, `:23-25` (+SRV-05)
- [x] `metadata` invalid JSON → 400: `tests/test_errors.py:34-35` (+SRV-06)
- [x] `metadata` non-object (valid JSON, wrong shape) → 400: `tests/test_errors.py:44-45`
- [x] audio > max → 413: `tests/test_errors.py:54-55` (+SRV-07)
- [x] pipeline raises → 500 + generic + stack in log: `tests/test_errors.py:64-68` (+SRV-08)
- [x] `metadata` absent → default `"pt"`: `tests/test_contract.py:36` (+SRV-04)
- [x] unexpected exception before pipeline (malformed multipart / missing file) → 400 generic JSON, never raw traceback: exact error-contract body asserted at `tests/test_errors.py:15`; the unhandled-Exception → 500 handler (`server/x9ai/app.py:97-101`) is not directly exercised (minor, non-blocking observation)

---

## Gate Check

- **Gate command**: `.venv/bin/python -m pytest && .venv/bin/ruff check . && .venv/bin/python -c "from x9ai.app import create_app; a = create_app(); assert [ (r.path, sorted(r.methods)) for r in a.routes if type(r).__name__ == 'APIRoute' ] == [('/process', ['POST'])]"` (tasks.md:37)
- **Result**: 31 passed, 0 failed, 0 skipped
- **Test count before feature**: 0 (no `server/` tree on `main`)
- **Test count after feature**: 31
- **Delta**: +31 (7 test modules; ≥31 required - no deletions)
- **Skipped tests**: none
- **Failures**: none
- **Warnings**: 1 deprecation (`fastapi.testclient`/httpx DeprecationWarning, third-party only) - not gating

---

## Fix Plans (if issues found)

None. No gaps, no surviving mutants.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| SRV-01..SRV-11 | Verified (spec.md:126-136) | ✅ Verified — confirmed by independent checks |

Traceability confirmed: 11 requirements, 11 mapped to tasks, 0 unmapped (spec.md:138). No spec.md status changes needed by this validation.

---

## Summary

**Overall**: ✅ Ready

**Spec-anchored check**: 11/11 ACs matched spec outcome | 0 spec-precision gaps
**Sensor**: 3/3 mutations killed
**Gate**: 31 passed, 0 failed, 0 skipped

**What works**: single `POST /process` route with §6.2 contract; sealed error mapping (400/413/500 generic JSON, §4.1 server-only diagnostics); swappable `Pipeline` seam (AD-004); SRV-10 timing and SRV-11 structured logging; 31 discriminating tests trace 1:1 to ACs.

**Issues found**: none blocking. One minor observation: generic 500 exception handler (`app.py:97-101`) has no direct test; malformed-multipart 400 path is covered with exact error-contract shape.

**Next steps**: none required; feature `server-api` verified. `nlp-pipeline` swaps the stub behind the same seam.