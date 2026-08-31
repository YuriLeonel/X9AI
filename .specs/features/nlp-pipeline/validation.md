# nlp-pipeline Validation

**Date**: 2026-08-30
**Spec**: `.specs/features/nlp-pipeline/spec.md`
**Diff range**: `main...HEAD` (ae67033..833968b)
**Verifier**: independent sub-agent (author ≠ verifier), re-verification round 2 after T6 fix (commit `833968b`)
**Result**: PASS

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1: whisper settings in config | ✅ Done | covered by test_config.py NLP-08 |
| T2: rule-based normalizer | ✅ Done | covered by test_normalizer.py NLP-10..14 |
| T3: lazy faster-whisper transcriber | ✅ Done | covered by test_transcriber.py NLP-05..09 |
| T4: composed RealPipeline | ✅ Done | covered by test_pipeline.py NLP-01..02, NLP-04 |
| T5: create_app default real pipeline | ✅ Done | adopted as default; covered by test_real_pipeline.py NLP-03 |
| T6: pin create_app default pipeline composition (fix from round-1 Verifier) | ✅ Done | `833968b` adds `test_create_app_default_normalizes_transcription`; kills the previously-surviving no-op-normalizer mutant (NLP-03) |

---

## Spec-Anchored Acceptance Criteria

### P1: Real Composed Pipeline

| Criterion (WHEN X THEN Y) | Spec-defined outcome | `file:line` + assertion | Result |
| ------------------------- | -------------------- | ----------------------- | ------ |
| NLP-01 Pipeline impl composes transcriber + normalizer, audio yields transcriber's raw through normalizer | process(audio,"pt") == "O é bom." from FakeTranscriber("o tipo então é bom") (spec Independent Test) | `tests/test_pipeline.py:44-46` - `assert isinstance(pipeline, Pipeline)` (implements seam); `tests/test_pipeline.py:49-51` - `assert pipeline.process(b"\x00","pt") == "O é bom."` | ✅ PASS |
| NLP-02 real pipeline returns transcriber+normalizer composed clean text | process returns normalized output (spec Independent Test "==") | `tests/test_pipeline.py:49-51` - `assert pipeline.process(b"\x00","pt") == "O é bom."`; `tests/test_pipeline.py:54-64` forwards `language` `received == {"language":"en"}` | ✅ PASS |
| NLP-03 create_app sets real pipeline as default, request with no injected pipeline served by transcription then normalization | default is RealPipeline (transcriber+normalizer); end-to-end normalized text for a request with NO injected pipeline | `tests/test_real_pipeline.py:30-38` - patches `x9ai.app.WhisperTranscriber` with `_FakeTranscriber()` (returns un-normalized `"o tipo então é bom"`), builds default `create_app()` with **no pipeline arg**, POSTs a clip, `assert response.json()["text"] == "O é bom."` (default's composition transcription→normalization is behavior-pinned) | ✅ PASS |
| NLP-04 transcriber raises → propagate to HTTP layer → 500 generic + logged stack | exception propagates uncaught from process; HTTP 500 + generic msg + server-side stack (SRV-08) | `tests/test_pipeline.py:67-70` - `with pytest.raises(RuntimeError, match="boom"): pipeline.process(...)` (uncaught); `tests/test_errors.py:58-68` - `response.status_code == 500`, `body == {"status":"error","message":"processing failed"}`, `"boom-internal-detail" in caplog.text` (generic + logged stack) | ✅ PASS |

### P1: Transcription via faster-whisper

| Criterion (WHEN X THEN Y) | Spec-defined outcome | `file:line` + assertion | Result |
| ------------------------- | -------------------- | ----------------------- | ------ |
| NLP-05 expose `Transcriber` abstraction, single method bytes+lang → raw text | abstract `Transcriber` uninstantiable (spec Independent Test) | `tests/test_transcriber.py:25-27` - `with pytest.raises(TypeError): Transcriber()` | ✅ PASS |
| NLP-06 WHER faster-whisper present → transcribe with model/device/compute | `model.transcribe(BytesIO(audio), language=lang)`, segments joined (AD-011) | `tests/test_transcriber.py:41-53` - `result == "ola 6 tudo bem"` from segment join; `captured == {"model":"medium","device":"auto","compute_type":"default"}`; `tests/test_transcriber.py:69-79` - `seen == {"language":"en"}` | ✅ PASS (guarded-by-design: the real faster-whisper path under `[whisper]` extra is not gate-run — spec Assumption "Real model in gates" = y) |
| NLP-07 WHER package absent → importing module + constructing succeed; only transcribe raises | import/construct OK w/o faster-whisper; transcribe on default factory raises ImportError | `tests/test_transcriber.py:30-33` - `"faster_whisper" not in sys.modules`; `tests/test_transcriber.py:82-85` - `with pytest.raises(ImportError): transcriber.transcribe(b"\x00","pt")`; `tests/test_real_pipeline.py:19-21` - `create_app()` boots | ✅ PASS |
| NLP-08 model/device/compute configurable via env, model default "medium" | defaults medium/auto/default; env overrides + blank/missing fallback (spec Assumptions) | `tests/test_config.py:34-38` - defaults `=="medium"/"auto"/"default"`; `:41-48` env read; `:51-58` unset fallback; `:61-68` blank fallback | ✅ PASS |
| NLP-09 report selected model name in transcriber config | operators can confirm active model | `tests/test_transcriber.py:36-38` - `WhisperTranscriber(settings=Settings(whisper_model="large-v3")).model_name == "large-v3"` | ✅ PASS |

### P1: Rule-Based PT-BR Normalization

| Criterion (WHEN X THEN Y) | Spec-defined outcome | `file:line` + assertion | Result |
| ------------------------- | -------------------- | ----------------------- | ------ |
| NLP-10 expose swappable `Normalizer` abstraction, single method raw→normalized | abstract `Normalizer` uninstantiable (spec Independent Test) | `tests/test_normalizer.py:8-10` - `with pytest.raises(TypeError): Normalizer()` | ✅ PASS |
| NLP-11 WHER filler from blacklist (`tipo`,`né`,`então`,`ééé`,`um`,`uh`) as case-insens whole word → remove | each of six fillers removed whole-word, case-insens (§9.2 exact list) | `tests/test_normalizer.py:13-20` per-filler `== "O é bom."/"Vamos."/"Vamos."/"Legal."/"Carro."/"Ok."`; `:23-24` case-insens `"TIPO oi ENTÃO bom" == "Oi bom."`; `:27-28` substring not removed `"mundo é bom" == "Mundo é bom."` | ✅ PASS |
| NLP-12 WHER first word no leading capital → capitalize first char | `"o é bom" → "O é bom."` (spec Independent Test) | `tests/test_normalizer.py:31-32` - `== "O é bom."`; `:23-24` mid-word case-insens | ✅ PASS |
| NLP-13 WHER sentence not ending in `.`,`!`,`?` → append `.` | append `.` only when no ending punct; preserve existing `.!?` | `tests/test_normalizer.py:35-36` - `"ola mundo" == "Ola mundo."`; `:39-43` `"Olá."/"Olá!"/"Olá?"` unchanged; `:56` `"o   tipo   é" == "O é."` | ✅ PASS |
| NLP-14 normalization deterministic | same input → identical output | `tests/test_normalizer.py:46-49` - `normalize(text) == normalize(text)` | ✅ PASS |

**Status**: ✅ 14/14 ACs matched spec outcome; 0 gaps.

---

## Discrimination Sensor

Isolated scratch `/tmp/x9ai-reverify` (`git worktree add /tmp/x9ai-reverify HEAD`, detached 833968b), mutated, pytest run there via `PYTHONPATH=/tmp/x9ai-reverify/server`, then discarded (`git worktree remove --force`). Real tree unmodified (porcelain before/after identical). Round-2 re-ran the previously-surviving no-op-normalizer mutant plus spot-check mutants.

| # | Mutation | Scratch file:line | Description | Killed? |
| - | -------- | ----------------- | ----------- | ------- |
| 1 | `server/x9ai/app.py:84` | `_NoOpNormalizer` class + `_real_pipeline` returns `RealPipeline(WhisperTranscriber(settings), _NoOpNormalizer())` | Default normalizer swapped for a **no-op** (returns input unchanged) — the previously-surviving mutant (Round-1 Mutant 6) | ✅ **KILLED** — `test_create_app_default_normalizes_transcription` fails (`assert 'o tipo então é bom' == 'O é bom.'`); 1 failed in test_real_pipeline.py |
| 2 | `server/x9ai/normalizer.py:10` | `_FILLER_PATTERN` dropped `\|tipo` | Filler `tipo` no longer removed | ✅ Killed (6 failures: normalizer + pipeline + real_pipeline end-to-end) |
| 3 | `server/x9ai/pipeline.py:31-33` | `RealPipeline.process` wrapped transcribe in `try/except: raw=""` | Transcriber exception swallowed | ✅ Killed (`test_real_pipeline_propagates_transcriber_exception` fails) |
| 4 | `server/x9ai/config.py:7` | `WHISPER_MODEL_DEFAULT = "base"` | Model default changed from `medium` | ✅ Killed (5 failures: config + transcriber) |

**Sensor result**: 4/4 mutations killed, 0 survived — including the previously-surviving no-op-normalizer default-composition mutant (now KILLED).

---

## Gate Check

- **Gate command** (Build, from tasks.md): `.venv/bin/python -m pytest -q && .venv/bin/ruff check . && .venv/bin/python -c "from x9ai.app import create_app; a = create_app(); assert isinstance(a, object)"`
- **Result**: 60 passed, 0 failed, 0 skipped, 1 warning (deprecation from fastapi/testclient); ruff clean ("All checks passed!"); `create_app()` boots without faster-whisper.
- **Test count**: 60 (was 59 pre-T6; +1 from `test_create_app_default_normalizes_transcription`)
- **Skipped**: none

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ flat modules, no extra abstractions |
| Surgical changes | ✅ T6 touches only `server/tests/test_real_pipeline.py` (+1 test, +1 import) and `tasks.md` (T6 record); no implementation change beyond existing defaults |
| No scope creep | ✅ T6 only pins default composition |
| Maps to NLP-03 | ✅ `test_create_app_default_normalizes_transcription` behavior-pins the default pipeline's transcriber→normalizer composition |
| Spec-anchored outcome check (values match spec) | ✅ asserts exact spec outcome `"O é bom."` against a default (no injected pipeline) |
| Every test maps to a spec AC / edge / Done-when | ✅ T6 test maps to NLP-03 Done-when |

---

## Edge Cases

- [x] Fillers-only / whitespace → empty: `test_normalizer.py:52-56` (`"tipo" == ""`, `"ééé uh" == ""`)
- [x] Already-terminated sentence keeps `.`, `!`, `?`: `test_normalizer.py:39-43`
- [x] Already-capitalized left unchanged: `test_normalizer.py:41-43` (`"Olá."` preserved)
- [x] English language same rules (`um`/`uh` removed, PT-BR pass): `test_normalizer.py:59-60` `"um uh oi" == "Oi."`
- [x] Empty/whitespace transcription → empty passed through (spec Assumption, empty audio 400): `test_errors.py:18-26`

---

## Summary

**Overall**: ✅ PASS

**Spec-anchored check**: 14/14 ACs matched spec outcome | 0 gaps
**Sensor**: 4/4 mutations killed | 0 survived (Round-2, incl. re-injection of the previously-surviving no-op-normalizer default-composition mutant — now KILLED)
**Gate**: 60 passed, 0 failed, 0 skipped

**Round-2 outcome**: The single gap found in round 1 — NLP-03 default-pipeline composition not behavior-pinned (a no-op normalizer at `server/x9ai/app.py` in `_real_pipeline` survived all tests) — is now closed by T6 (`833968b`). Re-injecting that exact no-op-normalizer mutant in the scratch worktree makes `test_create_app_default_normalizes_transcription` fail (`assert 'o tipo então é bom' == 'O é bom.'`), proving the default's real wiring is behavior-pinned. All 14 ACs (NLP-01..14) are covered with `file:line` assertion evidence; all injected behavior-level mutants are killed.

**Lessons**: None recorded this round — the feature passes clean (no surviving mutant, no gap). The two candidate lessons from round 1 (L-001, L-002) remain as candidates in `.specs/lessons.json`; no new lesson is warranted for a clean PASS.
