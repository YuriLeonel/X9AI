# X9AI — Spec-Driven State

Decisions log + handoff snapshot for the spec-driven workflow
(`tlc-spec-driven` skill). Source of truth for behavior is `docs/spec.md`; this file
tracks how the project decided to satisfy it.

## Decisions (AD-NNN)

Projects/commits must reference these IDs and update this log when a decision is recorded
(use the skill's `memory.md` workflow).

| ID   | Status | Decision |
|------|--------|----------|
| AD-001 | Accepted | Client implemented in Rust: portable exe, no .NET/Electron, minimal footprint |
| AD-002 | Accepted | Server is a lightweight Python + FastAPI microservice (Whisper PT-BR) |
| AD-003 | Accepted | Single HTTP boundary `POST /process` (multipart in → JSON out); no streaming in v1 |
| AD-004 | Accepted | Transcription runs local (privacy, zero cost); cloud is a complete swap across `/process`, never both in parallel |
| AD-005 | Accepted | v1 target Windows only, single user, no auth / multi-tenant |
| AD-006 | Accepted | Clipboard write retried up to 3× at 50ms to survive OS lock contention |
| AD-007 | Accepted | Verification via golden-transcript oracle: ≥90% semantic similarity + structural checks + keyword presence (`docs/spec.md` §9) |
| AD-008 | Accepted | Normalization v1 is a deterministic rule-based PT-BR pass (filler removal, punctuation, casing) behind a swappable `Normalizer` interface; no local LLM in v1 |
| AD-009 | Accepted | Golden corpus built as pluggable dir + mock transcriber mode (pipeline validated against golden text without audio); real PT-BR clips recorded before final UAT |
| AD-010 | Accepted | Client core (state machine, retry, HTTP contract, parsing) is platform-agnostic and unit-tested on Linux; Windows glue (tray/hotkey/record/clipboard/notify) is cfg-gated, built on Windows |
| AD-011 | Accepted | Transcriber engine = `faster-whisper` (CTranslate2); model size env-configurable; stub implementation in tests for deterministic gates |
| AD-012 | Accepted | Git workflow: `main` trunk + one feature branch per TLC feature merged after its Verifier passes; one atomic Conventional Commit per task |
| AD-013 | Accepted | Windows client glue stack locked: `tray-icon` + `global-hotkey` + `cpal` + `arboard` + classic `Shell_NotifyIcon` balloon (no winrt-notification/AUMID); glue is `cfg(windows)`, Linux gates type-check it via `cargo check --target x86_64-pc-windows-gnu` |
| AD-014 | Accepted | Client server endpoint defaults to `http://127.0.0.1:8000`, overridable via `X9AI_SERVER_URL`; no config file in v1 |
| AD-015 | Accepted | `create_app` honors `Settings.from_env()` (env `WHISPER_MODEL`/`WHISPER_DEVICE`/`MAX_AUDIO_BYTES`/`ORACLE_EMBEDDING_MODEL`) rather than `Settings()` defaults; discovered 2026-09-02 during live E2E when `WHISPER_DEVICE=cpu` was ignored → CUDA `libcublas.so.12` crash. Requires restarting uvicorn after env change (settings read at app factory call) |

## Roadmap

Features (each: Specify → Design → Tasks → Execute → Verifier → merge to `main`):

1. `server-api` ✅ DONE — FastAPI `POST /process` HTTP boundary, JSON contract, error mapping, pipeline seam (stub), logs/timing; validated PASS (11/11 ACs, 31 tests, 3/3 sensor killed). (`docs/spec.md` §6, §4.1)
2. `nlp-pipeline` ✅ DONE — faster-whisper transcription + rule-based PT-BR normalization wired into the seam; injectable stub for gates. Validated PASS (14/14 ACs, 60 tests, 4/4 sensor killed). Merged to `main` (66c537d, PR #1). (§5)
3. `golden-oracle` ✅ DONE — oracle harness: ≥90% semantic similarity, structural checks, filler blacklist, keyword presence, corpus runner with mock mode. Validated PASS (16/16 ACs, 97 tests, 3/3 sensor killed). Merged to `main` (fd15708 via 6303183, PR #2). (§9)
4. `client` ✅ DONE, MERGED — Rust client: core (state machine, clipboard retry 3×50ms, HTTP client, parsing; tested on Linux) + cfg-gated Windows glue. (§3.1, §4, §7) — Merged to `main` via PR #3 (088fd9d, 4060531). Validated PASS (18/18 ACs, 72 tests, 3/3 sensor killed).

Execute order is dependency-safe: each branch starts from `main` after its dependency is merged.

## Handoff

- **State:** All 4 roadmap features merged to `main` (Client via PR #3, commit 4060531). Working tree clean except `server/x9ai/app.py` (see below).
- **Live E2E run (2026-09-02):** Installed `[whisper,oracle]` extras in `server/.venv` (faster-whisper 1.2.1, torch 2.14.0+cu130, sentence-transformers 6.0.1, ctranslate2 4.8.2). Generated 4 real PT-BR clips via Piper TTS (voice `pt_BR-faber-medium`, 16-bit mono 22050Hz) in `/tmp/x9ai_corpus/` (s01–s04.wav + golden.json). Full HTTP `POST /process` E2E works: real Whisper (`small`, device=cpu) transcribes all clips ~2.7s each; structural checks (§9.2) all PASS; semantic ≥0.90 PASS for s01/s02/s03.
- **Bug fixed (uncommitted):** `server/x9ai/app.py:89` used `Settings()` (ignores env) → `WHISPER_DEVICE=cpu` was ignored, server crashed on CUDA (`libcublas.so.12` not found, CUDA13 vs ctranslate2-needs-CUDA12 mismatch). Changed to `Settings.from_env()` (AD-015). 96/97 tests pass; the 1 failure (`test_transcriber.py::test_default_factory_raises_import_error_without_faster_whisper`) only passes when faster-whisper is NOT installed — a pre-existing env-sensitive test, now that extras are installed. **Not yet committed** — needs a Conventional Commit task.
- **CUDA caveat:** GPU path fails (`libcublas.so.12` missing; torch 2.14 brings CUDA13, ctranslate2 4.8.2 wants CUDA12). Ran on CPU for the live test. Fixing CUDA = separate concern (install CUDA12 runtime or pin ctranslate2).
- **Genuine s04 limitation:** Whisper misheard "trimestre" → "TMSP" on the short synthetic clip (similarity 0.764 < 0.90). Real accuracy limit on very short TTS audio, not a pipeline bug.
- **Two oracle spec gaps found (not yet decided/fixed):**
  1. **Embedding model accent-brittleness (§9.1):** default `paraphrase-multilingual-MiniLM-L12-v2` scores a single-accent difference (relatório vs relatorio) at only 0.676 < 0.90 → false failure whenever Whisper drops a PT-BR accent. `distiluse-base-multilingual-cased-v2` gives 0.962 on the same pair AND is more discriminative (unrelated sentences 0.230 vs 0.357). Candidate default change (`config.py:10`).
  2. **Keyword check accent-sensitivity (§9.3):** `keywords_present` (`oracle.py:106`) substrings without accent normalization, so "relatorio" vs "relatório" fails raw despite identical meaning. Whisper is accent-inconsistent (dropped accent on "relatorio" but kept "reunião"/"café"), so any fixed accent form yields false keyword failures for PT-BR.
  - Net effect: with accent-robust model + accent-tuned corpus, oracle = s01 0.962, s02 0.989, s03 1.000 (all PASS on §9.1+§9.2); only s04 (genuine mishear) + keyword accents keep CORPUS from a clean PASS.
- **Next step (options):** (a) apply the two oracle fixes as a proper spec-driven feature so a live v1 PASS is claimable, and commit the `app.py` fix (AD-015); or (b) leave as recorded findings. Corpus + clips reused from `/tmp/x9ai_corpus/` (note: `/tmp` is ephemeral).
- **Windows runtime smoke** (tray/hotkey/clipboard/toast) remains a documented post-merge manual step (AD-010). Client builds clean on Linux: 65 tests (58 lib + 7 integration), `cargo check --target x86_64-pc-windows-gnu` passes.
