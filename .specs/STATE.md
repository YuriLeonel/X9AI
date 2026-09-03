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

## Roadmap

Features (each: Specify → Design → Tasks → Execute → Verifier → merge to `main`):

1. `server-api` ✅ DONE — FastAPI `POST /process` HTTP boundary, JSON contract, error mapping, pipeline seam (stub), logs/timing; validated PASS (11/11 ACs, 31 tests, 3/3 sensor killed). (`docs/spec.md` §6, §4.1)
2. `nlp-pipeline` ✅ DONE — faster-whisper transcription + rule-based PT-BR normalization wired into the seam; injectable stub for gates. Validated PASS (14/14 ACs, 60 tests, 4/4 sensor killed). Merged to `main` (66c537d, PR #1). (§5)
3. `golden-oracle` ✅ DONE — oracle harness: ≥90% semantic similarity, structural checks, filler blacklist, keyword presence, corpus runner with mock mode. Validated PASS (16/16 ACs, 97 tests, 3/3 sensor killed). Merged to `main` (fd15708 via 6303183, PR #2). (§9)
4. `client` ✅ VALIDATED, PENDING MERGE — Rust client: core (state machine, clipboard retry 3×50ms, HTTP client, parsing; tested on Linux) + cfg-gated Windows glue. (§3.1, §4, §7) — Branch `feature/client`; validated PASS (18/18 ACs, 72 tests, 3/3 sensor killed); awaiting push + PR (`gh pr create`, no merge).

Execute order is dependency-safe: each branch starts from `main` after its dependency is merged.

## Handoff

- `server-api` and `nlp-pipeline` and `golden-oracle` all merged to `main` (66c537d, fd15708). 97 passing tests at `server/.venv`.
- `client` feature: implementation complete on `feature/client` (16/16 tasks done, 18/18 ACs ✅ Verified). Verifier PASS — 72 tests (58 lib unit + 7 integration + 7 doc), Build gate (fmt + clippy -D warnings + test + `cargo check --target x86_64-pc-windows-gnu`) exit 0, discrimination sensor 3/3 killed. Evidence: `.specs/features/client/validation.md`. Local branch commits up to `6ae7d89`; NOT yet pushed, PR not opened (requires explicit go-ahead).
- Next step: with user go-ahead — `git push https://github.com/YuriLeonel/X9AI.git feature/client` then `gh pr create` (NO merge; UI drop-down stays open; PR link is the finish gate).
- Pre-UAT step recorded in the §9 evidence review: capture real PT-BR clips and run `python -m x9ai.oracle run <corpus>` with `[whisper,oracle]` installed before claiming a live v1 PASS. Windows runtime smoke (tray/hotkey/clipboard/toast) is a documented post-merge manual step (AD-010, spec §Success Criteria).
- Reconcile this snapshot against git `status` and `tasks.md` on resume — evidence wins over a stale snapshot.
