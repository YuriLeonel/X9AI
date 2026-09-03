# client Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/client/design.md`
**Status**: Approved

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: `AGENTS.md` (AD-001 Rust client, AD-010 platform-agnostic core unit-tested on Linux + cfg-gated glue; §3 stack invariants), `docs/spec.md` §4/§6/§9, `.specs/features/client/{context,design}.md` (AD-013 glue stack + `cargo check --target x86_64-pc-windows-gnu` gate, AD-014 endpoint). No existing Rust code in the repo (client is the first crate) and no Rust CI config; strong defaults apply to the glue layer (type-check + manual Windows UAT per AD-010).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| State machine (`state.rs`) | unit | All branches; 1:1 to CLI-01..04; every listed edge (double-tap, tap during Processing, single-flight) | `client/src/core/state.rs` (`#[cfg(test)]` inline) | `cargo test -q --lib` |
| WAV writer + metadata (`audio.rs`) | unit | Byte-asserted RIFF/WAVE/fmt headers, sample rate + block alignment, JSON bytes exact, 300s cap const (CLI-08/10) | `client/src/core/audio.rs` (`#[cfg(test)]` inline) | `cargo test -q --lib` |
| Clipboard retry (`retry.rs`) | unit | 1:1 to CLI-15/16; attempt counts + recorded 50ms delays via injected sleeper; all branches (success 1st/2nd/3rd, all-fail) | `client/src/core/retry.rs` (`#[cfg(test)]` inline) | `cargo test -q --lib` |
| Notice mapping (`notify.rs`) | unit | CLI-17/18 exact PT-BR strings; notifier fired with right args | `client/src/core/notify.rs` (`#[cfg(test)]` inline) | `cargo test -q --lib` |
| HTTP parse + endpoint (`http.rs`) | unit | CLI-12/14 fixtures: success/error/malformed JSON, default endpoint, `X9AI_SERVER_URL` override | `client/src/core/http.rs` (`#[cfg(test)]` inline) | `cargo test -q --lib` |
| ReqwestProcessor wire (`http.rs`) | integration | CLI-11/13/14: stub TCP listener asserts multipart fields (audio_file + metadata), canned success/error/status/malformed/connect bodies | `client/tests/process_integration.rs` | `cargo test -q` |
| App orchestration (`app.rs`) | unit | All branches; tooltip labels (CLI-06/07); effects for every trigger incl. zero-byte capture (CLI-09); single-flight | `client/src/core/app.rs` (`#[cfg(test)]` inline) | `cargo test -q --lib` |
| Non-blocking dispatch (`runner.rs`) | unit | CLI-05: spawn returns before injected blocking closure completes | `client/src/core/runner.rs` (`#[cfg(test)]` inline) | `cargo test -q --lib` |
| Windows glue (`glue/*.rs`) | none | - (cross-target type-check + manual Windows UAT, AD-010) | `client/src/glue/` | Build gate (see below) |
| Crate scaffold / manifest / binary | none | - (build gate only) | `client/Cargo.toml`, `client/src/main.rs`, `client/src/lib.rs` | Build gate (see below) |

## Gate Check Commands

> Generated from codebase - confirm before Execute. All gates run from `client/` (the crate root). `cargo fmt --check` + `cargo clippy -- -D warnings` are the lint/format gates; the cross-target `cargo check --target x86_64-pc-windows-gnu` proves the cfg(windows) glue compiles (AD-013) — it is the build gate for every glue task.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After tasks with unit tests only | `cargo test -q --lib` |
| Full | After tasks with integration tests | `cargo test -q` |
| Build | After config/entity-only tasks, glue tasks, and phase completion | `cargo fmt --check && cargo clippy -- -D warnings && cargo test -q && cargo check --target x86_64-pc-windows-gnu` |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order. Cross-phase dependencies are satisfied by backward task ordering (each phase must finish before the next starts).

### Phase 1: Scaffold

The crate must compile on Linux (`cargo test`, empty suite) AND type-check for Windows before any feature work, so every later gate is meaningful.

```
T1
```

### Phase 2: Core primitives (unit-tested on Linux)

Independent pure modules; each supplies AD-010's Linux-tested core.

```
T2 · T3 · T4 · T5 · T6   (parallel; all depend on T1)
```

### Phase 3: Orchestration + HTTP boundary

`app.rs` composes the primitives into the §4 loop; `runner.rs` proves CLI-05; the ReqwestProcessor wire is proven against a stub TCP listener.

```
T7 · T8 · T9   (parallel; depend backward on Phases 1-2)
```

### Phase 4: Windows glue (type-check only)

Each glue task is gated by the cross-target check; `app_loop.rs` binds every core seam to its Windows implementation.

```
T10 → T11
T10 → T12
T10 → T15
T11 → T15
T12 → T15
T13 → T15
T14 → T15
T15 → T16
```

---

## Task Breakdown

### Phase 1: Scaffold

### T1: Scaffold crate with cfg-gated glue

**What**: Create the `client/` crate: `Cargo.toml` with core deps (`serde`, `serde_json`, `reqwest` blocking + multipart + json, `default-features=false`) and `[target.'cfg(windows)'.dependencies]` (`tray-icon`, `global-hotkey`, `cpal`, `arboard`, `windows-sys` with `Win32_Foundation`, `Win32_UI_WindowsAndMessaging`, `Win32_UI_Shell`); `src/lib.rs` declaring `pub mod core;` and `#[cfg(target_os = "windows")] pub mod glue;`; skeleton `src/core/{state,audio,http,retry,notify,app,runner}.rs` (empty modules) and `src/glue/{win_loop,tray,hotkey,recorder,clipboard,app_loop}.rs` + `glue/mod.rs` with a placeholder `pub fn run() -> Result<(), String> { Ok(()) }`; `src/main.rs` calling `glue::run()` on Windows and printing "X9AI client is Windows-only" otherwise.
**Where**: `client/Cargo.toml`
**Depends on**: None
**Reuses**: none (first Rust code in repo)
**Requirement**: - (build/scaffold)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `cargo build` succeeds on Linux (Windows deps not compiled on the host target)
- [x] `cargo check --target x86_64-pc-windows-gnu` succeeds (cfg(windows) skeleton + placeholder `run()` type-check)
- [x] `cargo test -q` on Linux reports zero test binaries failing (0 tests - no silent deletions introduced later are possible from here)
- [x] Build gate passes: `cargo fmt --check && cargo clippy -- -D warnings && cargo test -q && cargo check --target x86_64-pc-windows-gnu`
- [x] Test count: 0 tests pass (scaffold - no logic yet)

**Tests**: none
**Gate**: build

**Commit**: `build(client): scaffold crate with cfg-gated windows glue`

---

### Phase 2: Core primitives (unit-tested on Linux)

### T2: Add core state machine

**What**: Implement `src/core/state.rs`: `State { Idle, Recording, Processing }`, `Trigger { Hotkey, RecordingDone(Result<Vec<u8>, RecError>), ProcessOutcome(ProcessOutcome) }`, `ProcessOutcome { Success { text }, Error }`, and `transition()` applying the guard table (CLI-01/02/03: `Idle+Hotkey→Recording`, `Recording+Hotkey→Processing`, `Processing+Hotkey→ignored`; CLI-04: at most one recording).
**Where**: `client/src/core/state.rs`
**Depends on**: T1
**Reuses**: module skeleton from T1
**Requirement**: CLI-01, CLI-02, CLI-03, CLI-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Every legal transition moves state and returns the matching effect
- [x] `Processing + Hotkey` and double-taps leave state unchanged (CLI-02/03)
- [x] Second recording cannot start while one is active (CLI-04)
- [x] Gate check passes: `cargo test -q --lib`
- [x] Test count: 12 tests in `state.rs` pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(client): add core state machine`

---

### T3: Add wav writer and metadata builder

**What**: Implement `src/core/audio.rs`: `pcm_to_wav16(mono: &[f32], sample_rate: u32) -> Vec<u8>` (RIFF/WAVE/fmt 16-bit PCM mono/data, f32→i16 clipped), `metadata_json(timestamp: u64) -> String` (`{"language":"pt","client_timestamp":<ts>}`), and `const MAX_RECORD_SECONDS: u32 = 300`.
**Where**: `client/src/core/audio.rs`
**Depends on**: T1
**Reuses**: module skeleton from T1; field names from `server/x9ai/app.py`/`schemas.py`
**Requirement**: CLI-08, CLI-10

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] WAV header bytes asserted: `RIFF`/`WAVE`/`fmt ` magic, PCM16 (audio_format=1), mono (channels=1), supplied sample rate, block align = 2, data length = samples*2
- [x] Sample conversion clips at ±1.0 → i16 max/min and interleaves mono samples
- [x] `metadata_json` produces the exact `{"language":"pt","client_timestamp":<ts>}` bytes
- [x] `MAX_RECORD_SECONDS == 300`
- [x] Gate check passes: `cargo test -q --lib`
- [x] Test count: 9 tests in `audio.rs` pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(client): add wav writer and metadata builder`

---

### T4: Add notice mapping and notifier trait

**What**: Implement `src/core/notify.rs`: `enum Notice { Success, Error }`, `notice_text(n) -> &'static str` returning exactly `"Pronto para colar!"` and `"Falha no processamento. Verifique a conexão com o servidor."`, and `trait Notifier { fn show(&self, title: &str, body: &str); }`.
**Where**: `client/src/core/notify.rs`
**Depends on**: T1
**Reuses**: module skeleton from T1; PT-BR strings per `docs/spec.md` §4.1
**Requirement**: CLI-17, CLI-18

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `notice_text(Notice::Success)` == "Pronto para colar!"
- [x] `notice_text(Notice::Error)` == "Falha no processamento. Verifique a conexão com o servidor."
- [x] A fake `Notifier` records exactly one `show` with (title, body) derived from `notice_text`
- [x] Gate check passes: `cargo test -q --lib`
- [x] Test count: 4 tests in `notify.rs` pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(client): add notice mapping and notifier trait`

---

### T5: Add clipboard retry policy

**What**: Implement `src/core/retry.rs`: `trait ClipboardSink { fn set(&mut self, text: &str) -> Result<(), ClipError>; }`, `trait Sleeper { fn sleep(&self, ms: u64); }`, and `write_with_retry(sink, text, sleeper, attempts, delay_ms)` with `const CLIPBOARD_ATTEMPTS: usize = 3` and `const CLIPBOARD_DELAY_MS: u64 = 50` (CLI-15); returns final error only when all attempts fail (CLI-16).
**Where**: `client/src/core/retry.rs`
**Depends on**: T1
**Reuses**: module skeleton from T1; AD-006 contract (`docs/spec.md` §4.3)
**Requirement**: CLI-15, CLI-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Success on the 1st/2nd/3rd attempt returns `Ok` and stops retrying (failing sink records attempt count)
- [x] A recorded `Sleeper` proves exactly `attempts-1` sleeps of `delay_ms` between attempts
- [x] All 3 attempts failing returns the error and calls `set` exactly 3 times (CLI-16)
- [x] Defaults: `CLIPBOARD_ATTEMPTS == 3`, `CLIPBOARD_DELAY_MS == 50`
- [x] Gate check passes: `cargo test -q --lib`
- [x] Test count: 7 tests in `retry.rs` pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(client): add clipboard retry policy`

---

### T6: Add /process response parsing and endpoint config

**What**: Implement the pure contract of `src/core/http.rs`: `enum ProcError` (non-2xx, error-status, malformed JSON, io/connect/timeout), `fn endpoint_from_env(env: Option<&str>) -> String` (default `http://127.0.0.1:8000`), `fn parse_response(bytes: &[u8]) -> Result<String, ProcError>` mirroring `server/x9ai/schemas.py` (`{status:success,text}` vs `{status:error,message}`), and `trait Processor { fn process(&self, wav: Vec<u8>, metadata: &str) -> Result<String, ProcError>; }`.
**Where**: `client/src/core/http.rs`
**Depends on**: T1
**Reuses**: field names/JSON from `server/x9ai/app.py` + `schemas.py`
**Requirement**: CLI-12, CLI-14 (parse + endpoint legs)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `endpoint_from_env(None)` and a blank env both yield `http://127.0.0.1:8000`; a set `X9AI_SERVER_URL` overrides it (CLI-12)
- [x] `parse_response` returns `text` on `{"status":"success","text":...}`, and `ProcError` on `status:"error"`, non-2xx status line, malformed JSON, and missing `text` (CLI-14)
- [x] `Processor` trait exists with the signature above
- [x] Gate check passes: `cargo test -q --lib`
- [x] Test count: 8 tests in `http.rs` pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(client): add /process response parsing and endpoint config`

---

### Phase 3: Orchestration + HTTP boundary

### T7: Add reqwest processor with stub-listener integration tests

**What**: Implement `ReqwestProcessor` in `src/core/http.rs`: `reqwest::blocking` `POST {endpoint}/process` with `multipart::Form` (`Part::bytes("audio_file", wav)` + `Part::text("metadata", meta)`), 60s timeout, status/`status:"error"`/malformed/connect mapping to `ProcError`. Add `client/tests/process_integration.rs` spinning a `TcpListener` stub that asserts the multipart payload (two fields, correct boundary, `audio_file` = WAV bytes, `metadata` decodes to JSON with `language` and `client_timestamp`) and returns canned success/error/non-2xx/malformed bodies.
**Where**: `client/src/core/http.rs`
**Depends on**: T6
**Reuses**: `endpoint_from_env`, `parse_response`, `Processor` from T6; serde/serde_json from T1
**Requirement**: CLI-11, CLI-13, CLI-14 (wire legs)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Stub listener records one `POST` to `/process` with multipart containing exactly fields `audio_file` (raw WAV bytes) and `metadata` (JSON with `language:"pt"` and integer `client_timestamp`) - CLI-11
- [x] 2xx+success body → `Ok(text)` (CLI-13); `status:"error"`, 4xx/5xx, malformed JSON, and connection-refused → `ProcError` (CLI-14)
- [x] Uses `endpoint_from_env` output as the base URL; hits `{endpoint}/process`
- [x] Full gate passes: `cargo test -q` (integration test runs)
- [x] Test count: 7 tests pass in `process_integration.rs` (no silent deletions); unit suite stays green

**Tests**: integration
**Gate**: full

**Commit**: `feat(client): add reqwest processor with stub-listener integration tests`

---

### T8: Add app orchestration and tooltip labels

**What**: Implement `src/core/app.rs`: `fn ui_tooltip(state: &State) -> &'static str` (`Idle` → "X9AI", `Recording` → "Recording…", `Processing` → "Processing…"), and `struct App` with `on_hotkey()`, `on_recording_ready(Result<Vec<u8>, RecError>)`, `on_process_outcome(ProcessOutcome)` returning `Effect { BeginRecording, StopAndProcess{wav,meta}, Ignore, WriteClipboard{text}, Notify(Notice), RenderTooltip(&'static str), Quit }`, binding `State<->Effect` per §4 flow 1-5 (incl. zero-byte capture → generic error, no HTTP, CLI-09).
**Where**: `client/src/core/app.rs`
**Depends on**: T2, T3, T4
**Reuses**: `State`/`Trigger` (T2), `metadata_json` (T3), `Notice`/`notice_text` (T4)
**Requirement**: CLI-06, CLI-07, CLI-09 (orchestration legs)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `ui_tooltip` returns exactly "X9AI" / "Recording…" / "Processing…" per state (CLI-06/07)
- [x] Hotkey in `Idle` → `BeginRecording`; hotkey in `Recording` → `StopAndProcess` (with `metadata_json`); hotkey in `Processing` → `Ignore` (single-flight, CLI-04)
- [x] Zero-byte capture → `Notify(Error)` and NO `StopAndProcess` (no HTTP, CLI-09); healthy capture → `StopAndProcess`
- [x] `ProcessOutcome::Success` → `WriteClipboard`; `ProcessOutcome::Error` → `Notify(Error)`, never `WriteClipboard`
- [x] Success also renders `RenderTooltip` reset; every failure lands on the generic error (CLI-18 mapping)
- [x] Gate check passes: `cargo test -q --lib`
- [x] Test count: 13 tests in `app.rs` pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(client): add app orchestration and tooltip labels`

---

### T9: Add non-blocking processing dispatcher

**What**: Implement `src/core/runner.rs`: `fn spawn_processing<F>(f: F) where F: FnOnce() + Send + 'static` wrapping `std::thread::spawn`, returning as soon as the thread is spawned.
**Where**: `client/src/core/runner.rs`
**Depends on**: T1
**Reuses**: module skeleton from T1 (std only)
**Requirement**: CLI-05

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] A test spawns a closure that blocks on a channel; `spawn_processing` returns while the closure is still blocked (CLI-05)
- [x] The spawned closure runs to completion on a separate thread (flag set + channel release)
- [x] Gate check passes: `cargo test -q --lib`
- [x] Test count: 2 tests in `runner.rs` pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(client): add non-blocking processing dispatcher`

---

### Phase 4: Windows glue (type-check only)

### T10: Add windows message loop glue

**What**: Implement `src/glue/win_loop.rs`: register window class `X9AITrayWindow`, create a message-only window (`HWND_MESSAGE`), run `GetMessage`/`DispatchMessage` pumping on the owning thread, and post `UiEvent` to the app channel on quit.
**Where**: `client/src/glue/win_loop.rs`
**Depends on**: T1
**Reuses**: placeholder `glue/mod.rs` from T1; `windows-sys` features from Cargo.toml
**Requirement**: - (glue infrastructure; EDGE registration-failure path)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Cross-target build gate passes: `cargo check --target x86_64-pc-windows-gnu` (full Build gate incl. Linux `cargo test`)
- [x] Pump loop is structured so tray-icon + global-hotkey event delivery (both require a pump on their owning thread) can attach
- [x] Test count: 0 runtime tests on Linux (type-check + manual UAT per AD-010)

**Tests**: none
**Gate**: build

**Commit**: `feat(client): add windows message loop glue`

---

### T11: Add global hotkey glue

**What**: Implement `src/glue/hotkey.rs`: `GlobalHotKeyManager::new()`, `HotKey::new(Some(Modifiers::CONTROL | Modifiers::ALT), Code::Space)`, register, and forward `Hotkey` presses into the app channel; registration failure → error notice + exit (EDGE).
**Where**: `client/src/glue/hotkey.rs`
**Depends on**: T10
**Reuses**: T10's pump thread on which the manager is created
**Requirement**: - (hotkey; EDGE registration failure → error + exit)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Cross-target build gate passes: `cargo check --target x86_64-pc-windows-gnu` + Linux full Build gate
- [x] Fixed binding `Ctrl+Alt+Space`, no rebind UI (assumption; "n" confirmed)
- [x] Test count: 0 runtime tests on Linux (type-check + manual UAT per AD-010)

**Tests**: none
**Gate**: build

**Commit**: `feat(client): add global hotkey glue`

---

### T12: Add tray, tooltip, and balloon glue

**What**: Implement `src/glue/tray.rs`: `TrayIconBuilder` with `Icon::from_rgba`, menu ("Sair" always; "Parar gravação" only while Recording), tooltip fed by `core::app::ui_tooltip` (CLI-06/07), and `Shell_NotifyIcon(NIM_ADD + NIF_INFO + NIM_DELETE)` balloon using `core::notify::notice_text` (CLI-17/18).
**Where**: `client/src/glue/tray.rs`
**Depends on**: T4, T8, T10
**Reuses**: `ui_tooltip` (T8), `Notice`/`notice_text` (T4), T10's window as balloon anchor
**Requirement**: CLI-06, CLI-07, CLI-17, CLI-18

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Cross-target build gate passes: `cargo check --target x86_64-pc-windows-gnu` + Linux Full gate
- [x] Tooltip states wired to `ui_tooltip` (Recording…/Processing…), balloon bodies wired to `notice_text` (CLI-17/18 strings)
- [x] Menu model maps "Sair" → `UiEvent::Quit`, "Parar gravação" → stop-recording event
- [x] Test count: 0 runtime tests on Linux (type-check + manual UAT; Win11 balloon-suppression risk documented in design)

**Tests**: none
**Gate**: build

**Commit**: `feat(client): add tray, tooltip, and balloon glue`

---

### T13: Add cpal recorder glue

**What**: Implement `src/glue/recorder.rs`: open the default input device requesting 16 kHz mono; on rejection fall back to `default_input_config()` and write the WAV at the true rate; accumulate f32 samples; on stop or the 300s cap emit `RecordingDone` with `pcm_to_wav16` bytes (CLI-08/10); zero-byte capture → error result (CLI-09).
**Where**: `client/src/glue/recorder.rs`
**Depends on**: T3
**Reuses**: `pcm_to_wav16`, `MAX_RECORD_SECONDS` (T3)
**Requirement**: CLI-08, CLI-09, CLI-10

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Cross-target build gate passes: `cargo check --target x86_64-pc-windows-gnu` + Linux Full gate
- [x] 16 kHz mono preferred; device-default fallback paths compile (true-rate WAV header)
- [x] 300s cap route emits `RecordingDone` exactly like a manual stop (CLI-10); empty capture routes to `RecordingDone(Err)` (CLI-09)
- [x] Test count: 0 runtime tests on Linux (type-check + manual UAT per AD-010)

**Tests**: none
**Gate**: build

**Commit**: `feat(client): add cpal recorder glue`

---

### T14: Add arboard clipboard sink glue

**What**: Implement `src/glue/clipboard.rs`: `impl ClipboardSink for ArboardClipboard` wrapping `arboard::Clipboard::new().set_text(...)` so the core retry policy (T5) drives real clipboard writes.
**Where**: `client/src/glue/clipboard.rs`
**Depends on**: T5
**Reuses**: `ClipboardSink` (T5)
**Requirement**: CLI-15 (real sink)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Cross-target build gate passes: `cargo check --target x86_64-pc-windows-gnu` + Linux Full gate
- [x] Sink adapter implements `ClipboardSink::set` and maps `arboard::Error` to `ClipError`
- [x] Test count: 0 runtime tests on Linux (type-check + manual UAT per AD-010)

**Tests**: none
**Gate**: build

**Commit**: `feat(client): add arboard clipboard sink glue`

---

### T15: Wire windows app loop

**What**: Implement `src/glue/app_loop.rs`: connect everything on the main thread - select over the `UiEvent` channel, drive the core `App`, apply effects (tooltip via `TrayHandle`, clipboard via retry over the real sink, balloon via `Shell_NotifyIcon`, spawn recorder + worker threads via `spawn_processing`, quit on "Sair").
**Where**: `client/src/glue/app_loop.rs`
**Depends on**: T7, T8, T9, T10, T11, T12, T13, T14
**Reuses**: `App`/`Effect` (T8), `spawn_processing` (T9), `ReqwestProcessor` (T7), `write_with_retry` (T5), all glue modules
**Requirement**: CLI-05 (dispatch glue), CLI-13/14 (clipboard vs error wiring), EDGEs

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Cross-target build gate passes: `cargo check --target x86_64-pc-windows-gnu` + Linux Full gate
- [x] Hotkey while Recording triggers stop → worker request; `Successful` outcome writes clipboard (3×50ms retry) + Success balloon; any error → Error balloon only (CLI-13/14/17/18)
- [x] Main loop never blocks on the network (request runs on `spawn_processing` thread) - CLI-05
- [x] "Sair" (and EDT registration failure) → clean exit
- [x] Test count: 0 runtime tests on Linux (type-check + manual UAT per AD-010)

**Tests**: none
**Gate**: build

**Commit**: `feat(client): wire windows app loop`

---

### T16: Wire glue::run and binary entry

**What**: Replace the T1 placeholder: `glue/mod.rs::run()` becomes `app_loop::run()` and `src/main.rs` Windows branch calls it, returning process exit codes; Linux branch keeps the "Windows-only" stub.
**Where**: `client/src/glue/mod.rs`
**Depends on**: T15
**Reuses**: `app_loop::run` (T15)
**Requirement**: - (binary wiring)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Cross-target build gate passes: `cargo check --target x86_64-pc-windows-gnu` + Linux Full gate
- [x] `glue::run()` delegates to `app_loop::run`; `main.rs` dispatches on platform
- [x] Test count: 0 runtime tests on Linux (type-check + manual UAT per AD-010)

**Tests**: none
**Gate**: build

**Commit**: `feat(client): wire glue::run and binary entry`

---

## Phase Execution Map

Visual representation of task ordering. Phases run in sequence, and tasks within a phase run in order:

```
Phase 1 → Phase 2 → Phase 3 → Phase 4

Phase 1:  T1
Phase 2:  T2 · T3 · T4 · T5 · T6
Phase 3:  T7 · T8 · T9

Phase 4:
T10 → T11
T10 → T12
T10 → T15
T11 → T15
T12 → T15
T13 → T15
T14 → T15
T15 → T16
```

Execution is strictly sequential - there is no intra-phase parallelism. A single agent (or batch worker) works one task at a time, in order.

**How phase-based execution works:**

At Execute, the agent counts total tasks and packs phases into task-budgeted batches (~7 tasks per worker, whole phases). 16 tasks here pack as **Batch 1 = Phases 1-3 (9 tasks)** and **Batch 2 = Phase 4 (7 tasks)**; the phase-4 batch carries most of the cross-target risk because every glue task's gate is the Windows type-check. Because the glue depends on precise core seams (traits, enums, effect types) and every gate involves a toolchain-heavy `cargo` run, execution happens inline in the main window with one tightly-controlled worker - no sub-agents spawned (see `references/sub-agents.md`).

---

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: scaffold crate + manifest + skeletons | 1 crate bootstrap | ✅ Granular (deliberately multi-file: the crate must exist to test) |
| T2: state machine | 1 file, 1 concern | ✅ Granular |
| T3: wav writer + metadata | 1 file, 2 cohesive pure fns + const | ✅ Granular |
| T4: notice mapping + notifier trait | 1 file, 1 concern | ✅ Granular |
| T5: clipboard retry policy | 1 file, 3 interfaces | ✅ Granular (cohesive contract) |
| T6: /process parse + endpoint config | 1 file, pure contract | ✅ Granular |
| T7: reqwest processor + wire tests | 1 file + co-located tests | ✅ Granular (tests are co-located, not deferred) |
| T8: app orchestration + tooltip labels | 1 file, 1 concern | ✅ Granular |
| T9: non-blocking dispatcher | 1 file, 1 fn | ✅ Granular |
| T10: message loop glue | 1 file, 1 concern | ✅ Granular |
| T11: hotkey glue | 1 file, 1 concern | ✅ Granular |
| T12: tray + tooltip + balloon glue | 1 file, 1 concern | ✅ Granular |
| T13: recorder glue | 1 file, 1 concern | ✅ Granular |
| T14: clipboard sink glue | 1 file, 1 concern | ✅ Granular |
| T15: app loop wiring | 1 file, 1 concern | ✅ Granular |
| T16: run() + binary entry | 2 files, pure wiring | ✅ Granular (wiring is inherently multi-file but trivial) |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | T1 (start) | ✅ Match |
| T2 | T1 | T1→T2 (backward) | ✅ Match |
| T3 | T1 | T1→T3 (backward) | ✅ Match |
| T4 | T1 | T1→T4 (backward) | ✅ Match |
| T5 | T1 | T1→T5 (backward) | ✅ Match |
| T6 | T1 | T1→T6 (backward) | ✅ Match |
| T7 | T6 | T6→T7 (backward) | ✅ Match |
| T8 | T2, T3, T4 | T2/T3/T4→T8 (backward) | ✅ Match |
| T9 | T1 | T1→T9 (backward) | ✅ Match |
| T10 | T1 | T1→T10 (backward) | ✅ Match |
| T11 | T10 | T10→T11 | ✅ Match |
| T12 | T4, T8, T10 | T10→T12 (+T4/T8 backward) | ✅ Match |
| T13 | T3 | T3→T13 (backward) | ✅ Match |
| T14 | T5 | T5→T14 (backward) | ✅ Match |
| T15 | T7,T8,T9,T10,T11,T12,T13,T14 | T10→T15, T11→T15, T12→T15, T13→T15, T14→T15 (+T7/T8/T9 backward) | ✅ Match |
| T16 | T15 | T15→T16 | ✅ Match |

All `Depends on` entries have a diagram arrow (backward edges are satisfiable by phase ordering); every same-phase arrow matches a `Depends on`; no forward-phase dependencies (Phases run in order 1→2→3→4).

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1 | Scaffold/manifest/binary | none (build gate) | none | ✅ OK |
| T2 | State machine | unit | unit | ✅ OK |
| T3 | WAV writer + metadata | unit | unit | ✅ OK |
| T4 | Notice mapping | unit | unit | ✅ OK |
| T5 | Clipboard retry | unit | unit | ✅ OK |
| T6 | HTTP parse + endpoint | unit | unit | ✅ OK |
| T7 | ReqwestProcessor wire | integration | integration | ✅ OK |
| T8 | App orchestration | unit | unit | ✅ OK |
| T9 | Non-blocking dispatch | unit | unit | ✅ OK |
| T10 | Windows glue (win_loop) | none (type-check) | none | ✅ OK |
| T11 | Windows glue (hotkey) | none (type-check) | none | ✅ OK |
| T12 | Windows glue (tray) | none (type-check) | none | ✅ OK |
| T13 | Windows glue (recorder) | none (type-check) | none | ✅ OK |
| T14 | Windows glue (clipboard) | none (type-check) | none | ✅ OK |
| T15 | Windows glue (app_loop) | none (type-check) | none | ✅ OK |
| T16 | run() + binary | none (build gate) | none | ✅ OK |

No deferred tests; every code layer with a required test type carries its tests in-task.