# client Validation

**Date**: 2026-08-30
**Spec**: `.specs/features/client/spec.md`
**Diff range**: `2051472..HEAD` (8 client feature commits through `6ae7d89`)
**Verifier**: independent sub-agent (author ≠ verifier)

---

## Task Completion

| Task | Status     | Notes |
| ---- | ---------- | ----- |
| T1   | ✅ Done    | Scaffold crate + cfg-gated glue; cross-target type-checks |
| T2   | ✅ Done    | State machine; guard table + single-flight implemented |
| T3   | ✅ Done    | WAV writer + metadata; byte-asserted |
| T4   | ✅ Done    | Notice mapping + notifier trait |
| T5   | ✅ Done    | Clipboard retry 3×50ms with injected sleeper/delay |
| T6   | ✅ Done    | /process parse + endpoint config |
| T7   | ✅ Done    | Reqwest processor + stub-listener integration tests |
| T8   | ✅ Done    | App orchestration + tooltip labels |
| T9   | ✅ Done    | Non-blocking dispatcher (CLI-05) |
| T10  | ✅ Done    | win_loop (message-only window + pump) — type-check only |
| T11  | ✅ Done    | hotkey glue Ctrl+Alt+Space — type-check only |
| T12  | ✅ Done    | tray tooltip + balloon — type-check only |
| T13  | ✅ Done    | cpal recorder glue — type-check only |
| T14  | ✅ Done    | arboard clipboard sink — type-check only |
| T15  | ✅ Done    | app_loop wiring — type-check only |
| T16  | ✅ Done    | run() + binary entry — type-check only |

> **Bookkeeping note**: every per-task "Done when" checkbox in `tasks.md` is still
> unchecked (73 unchecked, 0 checked). The implementation itself passes all gates and
> ACs, but the implementer never ticked the per-task sign-off boxes. These should be
> ticked during closure bookkeeping (not a functional defect; I did not modify tasks.md,
> being scoped to validation.md + spec.md).

---

## Spec-Anchored Acceptance Criteria

All 18 ACs re-derived independently from `spec.md` only. Glue-layer ACs (CLI-06/07/17/18
wiring + T10..T16) are evidenced by code + the cross-target `cargo check --target
x86_64-pc-windows-gnu` passing (glue has zero runtime tests on Linux by design, AD-010;
runtime deferred to manual Windows UAT per design §Risks).

| Criterion (WHEN X THEN Y) | Spec-defined outcome | `file:line` + assertion | Result |
| ------------------------- | -------------------- | ----------------------- | ------ |
| CLI-01: core exposes exactly states Idle/Recording/Processing, transitions Idle→Recording→Processing→Idle | exactly 3 states; listed hotkey transitions | `client/src/core/state.rs:5-10` - `enum State { Idle, Recording, Processing }`; `state.rs:78-81` Idle+Hotkey→Recording; `state.rs:82-90` Recording+Hotkey→Processing; `state.rs:121-123` Processing→Idle; tests `state.rs:145-151,153-163,249-261` | ✅ PASS |
| CLI-02: hotkey WHILE Recording → stop + Processing | transitions to Processing | `state.rs:82-90`; `state.rs:153-163` — `assert_eq!(st.current(), State::Processing)` | ✅ PASS |
| CLI-03: hotkey WHILE Processing → ignore, stay Processing | stays Processing, Ignore | `state.rs:91-94`; `state.rs:165-173` — `assert_eq!(st.current(), State::Processing); matches!(e, Effect::Ignore)` | ✅ PASS |
| CLI-04: never >1 recording at a time | single-flight | `state.rs:287-297` — asserts stays Processing after hotkey + RecordingDone; also `state.rs:175-186` | ✅ PASS |
| CLI-05: /process dispatched without blocking the SM | transition returns before HTTP result | `runner.rs:5-10` (wraps `std::thread::spawn`); `runner.rs:19-38` — `done_rx.try_recv().is_err()` while closure blocked | ✅ PASS |
| CLI-06: tooltip "Recording…" while Recording | exact string | `app.rs:11` `TOOLTIP_RECORDING = "Recording…"`; `app.rs:14-20`; `app.rs:113-116` `assert_eq!(ui_tooltip(&State::Recording), "Recording…")` | ✅ PASS |
| CLI-07: tooltip "Processing…" while Processing | exact string | `app.rs:12`; `app.rs:117-120` `assert_eq!(ui_tooltip(&State::Processing), "Processing…")` | ✅ PASS |
| CLI-08: recording → WAV byte stream (RIFF header + PCM) | RIFF/WAVE/fmt PCM16 mono | `audio.rs:28-34` `pcm_to_wav16`; `audio.rs:46-63` — RIFF/WAVE/fmt magic, PCM(audio_format=1), mono(channels=1), sample_rate, block_align=2, data magic | ✅ PASS |
| CLI-09: zero audio bytes → generic error, NO HTTP | error notice; no request | `app.rs:67-72` maps empty wav to `RecordingDone(Err)`; `state.rs:111-115` → Idle+`Notify(Error)` (no StopAndProcess); `app.rs:165-176` — `matches!(effect, Effect::Notify(Notice::Error))` and no StopAndProcess | ✅ PASS |
| CLI-10: 300s cap → stop + process like manual stop | cap = 300; processed like manual | `audio.rs:2` `MAX_RECORD_SECONDS=300`; `audio.rs:115-118` `assert_eq!(MAX_RECORD_SECONDS, 300)`; `state.rs:200-211` cap path → StopAndProcess mirroring manual; `recorder.rs:30,44,52` uses cap | ✅ PASS |
| CLI-11: POST multipart to {endpoint}/process, fields audio_file + metadata | multipart 2 fields, audio_file=WAV, metadata JSON | `http.rs:86-96` builds Form with audio_file/metadata, posts `{base}/process`; `tests/process_integration.rs:156-186` — `fields.keys().len()==2`, `fields.get("audio_file")==wav`, metadata decodes JSON with `language`/`client_timestamp` | ✅ PASS |
| CLI-12: default http://127.0.0.1:8000, overridable via X9AI_SERVER_URL | default + override | `http.rs:1-2,31-36` `endpoint_from_env`; `http.rs:114-139` — default/blank→DEFAULT, set env→override | ✅ PASS |
| CLI-13: 2xx + success JSON → write text to clipboard | text lands on clipboard | `http.rs:43-57` parse success→text; `tests/process_integration.rs:169` `assert_eq!(result.unwrap(), "texto limpo")`; `state.rs:121-124` Success→`WriteClipboard{text}`; `app.rs:203-215` | ✅ PASS |
| CLI-14: non-2xx/error/malformed/connect/timeout → generic error, no clipboard | error notice; no clipboard | `http.rs:5-14` ProcError variants; parse tests `http.rs:141-168`; wire `tests/process_integration.rs:188-222` (non2xx=500, error-body, malformed, connection-refused→Transport); `state.rs:125-128` Error→`Notify(Error)` never WriteClipboard; `app.rs:225-233` | ✅ PASS |
| CLI-15: clipboard write up to 3 attempts, 50ms apart | 3 attempts @50ms | `retry.rs:2-4` `CLIPBOARD_ATTEMPTS=3`, `CLIPBOARD_DELAY_MS=50`; `retry.rs:21-41`; tests `retry.rs:97-144` — attempt counts + recorded `[50,50]` sleeps | ✅ PASS |
| CLI-16: all 3 clipboard attempts fail → generic error | error notice | `retry.rs:127-135` — all-fail → `is_err()`, 3 `set` calls; glue `app_loop.rs` maps `write_with_retry` Err→`Notice::Error` | ✅ PASS |
| CLI-17: Success → OS notification "Pronto para colar!" | exact PT-BR string | `notify.rs:9` `SUCCESS_TEXT`; `notify.rs:13-18`; `notify.rs:43-46` `assert_eq!(notice_text(Notice::Success), "Pronto para colar!")` | ✅ PASS |
| CLI-18: Error → OS notification "Falha...conexão com o servidor." | exact PT-BR string | `notify.rs:10` `ERROR_TEXT`; `notify.rs:48-54` `assert_eq!(notice_text(Notice::Error), "Falha no processamento. Verifique a conexão com o servidor.")` | ✅ PASS |

**Status**: ✅ All 18 ACs matched spec outcome, 0 spec-precision gaps (no vague assertions
left unanchored; every AC targeting a precise value has an exact-string/value assertion).

---

## Discrimination Sensor

Run in a temporary git worktree `/tmp/opencode/x9ai-verifier-42028` (`HEAD` = 6ae7d89);
the real tree was never modified (no `git stash`). Baseline `git status --porcelain`
was empty before and after; confirmed matching at the end.

| Mutation | File:line | Description | Killed? |
| -------- | --------- | ----------- | ------- |
| 1 | `client/src/core/state.rs:91-94` | Flipped the `Processing+Hotkey` guard to start a second recording (unguarded transition) | ✅ Killed — 5 tests fail (state/app: hotkey_in_processing_is_ignored, repeated_hotkey, no_more_than_one_recording, double_hotkey_never_opens_second, app::hotkey_in_processing) |
| 2 | `client/src/core/audio.rs:18` | Corrupted WAV header: channels mono(1)→stereo(2) | ✅ Killed — `core::audio::tests::wav_pcm16_mono_header_fields` fails |
| 3 | `client/src/core/retry.rs:34` | Removed the between-attempts-only sleep guard (sleeps on every failure) | ✅ Killed — `core::retry::tests::all_attempts_fail_returns_error` fails |

**Sensor depth**: lightweight (default; proportional to feature risk)
**Result**: 3/3 killed - **Result**: PASS ✅

---

## Gate Check

- **Gate command (Full)**: `cargo test -q` — **72 passed, 0 failed, 0 skipped**
  (58 lib unit + 7 integration + 7 doc + 0 main-bin)
- **Gate command (Build)**: `cargo fmt --check` (0) && `cargo clippy -- -D warnings` (0) && `cargo test -q` (0) && `cargo check --target x86_64-pc-windows-gnu` (0) — all exit 0.
  Cross-target check proves the cfg(windows) glue compiles (AD-013).
- **Test count before feature**: 0 (client is the first Rust crate in the repo; prior
  features were server/Python)
- **Test count after feature**: 72 (58 lib + 7 integration + 7 doc)
- **Delta**: +72 new tests
- **Skipped**: none. Windows glue has zero runtime tests on Linux by design (AD-010) —
  evidenced by cross-target type-check + deferred manual Windows UAT.
- **Failures**: none

> **Minor observation (not a defect)**: the per-task "Done when" predicted test counts
> in `tasks.md` (state=12, app=13; total 55) do not exactly match the actual counts
> (state=14, app=14; total 58). The delta is extra tests, strengthening discrimination —
> no test was deleted or weakened. Confirmed via sensor (all mutants killed).

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ |
| Surgical changes | ✅ |
| No scope creep | ✅ |
| Matches patterns | ✅ |
| Spec-anchored outcome check (asserted values match spec) | ✅ |
| Per-layer Coverage Expectation met (domain 1:1 ACs; routes happy+edge+error) | ✅ |
| Every test maps to a spec AC / edge case — no unclaimed tests | ✅ |
| Documented guidelines followed: `AGENTS.md` (AD-001, AD-010, AD-013, AD-014), `docs/spec.md` §4/§6, `.specs/features/client/design.md` | ✅ |

Every one of the 58 unit + 7 integration tests maps to a spec AC (CLI-01..18) or a
listed edge case / Done-when criterion; no orphan tests found.

---

## Edge Cases

- [x] Tray/hotkey registration failure → exit: `app_loop.rs` `hotkeys.register()?` propagates → `run()` returns Err → `main.rs` returns non-zero (design: "exits after error balloon attempt"; balloon itself is best-effort glue, manual UAT). Handled behaviorally.
- [x] Hotkey while Processing → ignore: CLI-03, `state.rs:91-94` + tests.
- [x] No input device at record start → generic error, return to Idle, no HTTP: `recorder.rs` `default_input_device().ok_or_else(...)`; `app_loop.rs` BeginRecording→spawn→`RecordingDone(Err)`; `state.rs:111-115` → Idle+Notify(Error); tests `state.rs:228-236`, `app.rs:194-201`.
- [x] 300s → auto-stop and process: CLI-10, `state.rs:200-211`, `recorder.rs` cap loop.
- [x] Success with empty `text` → still writes (empty) clipboard: `http.rs:49-52` `as_str` on `""` yields `Some("")` → `Ok("")` → WriteClipboard(empty); no size rejection (assumption honored).
- [x] WAV within 50MB given 300s cap → no client-side size rejection: `audio.rs:2` cap bounds samples; server enforces `max_audio_bytes`.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| CLI-01 | Pending | ✅ Verified |
| CLI-02 | Pending | ✅ Verified |
| CLI-03 | Pending | ✅ Verified |
| CLI-04 | Pending | ✅ Verified |
| CLI-05 | Pending | ✅ Verified |
| CLI-06 | Pending | ✅ Verified |
| CLI-07 | Pending | ✅ Verified |
| CLI-08 | Pending | ✅ Verified |
| CLI-09 | Pending | ✅ Verified |
| CLI-10 | Pending | ✅ Verified |
| CLI-11 | Pending | ✅ Verified |
| CLI-12 | Pending | ✅ Verified |
| CLI-13 | Pending | ✅ Verified |
| CLI-14 | Pending | ✅ Verified |
| CLI-15 | Pending | ✅ Verified |
| CLI-16 | Pending | ✅ Verified |
| CLI-17 | Pending | ✅ Verified |
| CLI-18 | Pending | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready

**Spec-anchored check**: 18/18 ACs matched spec outcome | 0 spec-precision gaps
**Sensor**: 3/3 mutations killed
**Gate**: Full 72 passed / 0 failed; Build (fmt+clippy+test+cross-check) all exit 0

**What works**: full client core validated on Linux (state machine, WAV writer, HTTP
boundary, clipboard retry, notify mapping, orchestration, non-blocking dispatch); the
cfg(windows) glue type-checks under `cargo check --target x86_64-pc-windows-gnu`; every
AC has precise `file:line` assertion evidence.

**Issues found**: none functional. Bookkeeping: `tasks.md` per-task "Done when" boxes are
all unticked (implementer sign-off), and the predicted test-count figures in the plan
(55) differ slightly from actual (58) — extra tests only, no weakening.

**Next steps**: tick per-task "Done when" boxes in `tasks.md` as closure bookkeeping;
run the post-merge manual Windows UAT (tray states, hotkey, clipboard, balloon) per
AD-010 / design §Risks.
