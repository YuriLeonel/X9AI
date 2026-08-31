# client Specification

## Problem Statement

The server side of X9AI is complete (`server-api`, `nlp-pipeline`, `golden-oracle` all
merged): a FastAPI `POST /process` boundary that transcribes and normalizes PT-BR audio,
plus an oracle that gates quality. What is missing is the thing the user touches — the
Rust client (§3.1): a silent system-tray utility that captures a spoken brain-dump behind
a global hotkey, sends the WAV to the server, and puts the normalized text on the
clipboard. This feature builds the client: a platform-agnostic core (state machine,
WAV writer, HTTP client, clipboard-retry policy, error mapping) validated on Linux
(AD-010), and cfg-gated Windows glue (tray, hotkey, recording, clipboard, toasts).

## Goals

- [ ] A `Recording → Processing → Success/Error → Idle` state machine (§4) with guarded transitions and at most one in-flight recording, unit-tested on Linux
- [ ] A `/process` HTTP client implementing §6 exactly (`audio_file` WAV + `metadata` JSON multipart; success/error parsing), endpoint `http://127.0.0.1:8000` overridable via `X9AI_SERVER_URL`
- [ ] Clipboard write reliability §4.3: up to 3 attempts at 50ms apart, deterministic on Linux via an injected sleeper
- [ ] The three §4.2 visual states rendered: tray tooltip "Recording…"/"Processing…" while active, one final Success/Error toast
- [ ] Windows glue (`tray-icon`, `global-hotkey`, `cpal`, `arboard`, `winrt-notification`) cfg-gated per AD-010; crate builds on Linux with a stub `main` and the glue type-checks under `cargo check --target x86_64-pc-windows-gnu` when the toolchain permits, otherwise a documented Windows build step

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Autostart with Windows (§3.1) | P2, deferred (user decision); registry tweak, not the core loop |
| Windows glue runtime UAT / hardware smoke | Manual on a Windows host (AD-010), like the oracle's real-clip pre-UAT step |
| Hotkey rebinding / multiple hotkeys | Fixed `Ctrl+Alt+Space` in v1; no settings UI |
| Config file / settings UI | `X9AI_SERVER_URL` env override suffices for single-user localhost (user decision) |
| Silence detection / network-drop recovery beyond the generic error (§8) | Explicitly deferred by §8 — happy path validates the loop |
| Anything server-side | Already shipped in prior features |
| Installer / MSI | §3.1: portable executable for v1 |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Hotkey | Fixed `Ctrl+Alt+Space`; registration failure → error toast at startup | No rebind UI in v1; Space is the natural "tap" key | n |
| Recording format | 16-bit PCM mono WAV, 16 kHz requested; fall back to device default and write WAV at the true rate | Whisper resamples at decode (`server/x9ai/transcriber.py`); §6.1 "standardized by the client" | n |
| Max recording duration | 300s hard cap → auto-stop and process like a manual stop | Keeps memory/server bound below `max_audio_bytes` (50 MB); distinct from §8-out-of-scope silence detection | n |
| Metadata | Always `{"language": "pt", "client_timestamp": <epoch s at record start>}` | §2 PT-BR primary; §6.1 sample; server defaults `language` to `pt` anyway | n |
| Success with empty `text` | Still writes (empty) clipboard | Deterministic, simple; silence handling is §8 out of scope | n |
| Notifications language | PT-BR: "Pronto para colar!" / "Falha no processamento. Verifique a conexão com o servidor." | §2 primary PT-BR; §4.1 English strings illustrative | n |
| Tray menu | "Sair" always; "Parar gravação" only while Recording | Hotkey-lost fallback to stop a recording | n |
| HTTP stack | `reqwest` blocking, `default-features = false` + `multipart` + `json` (no TLS) | localhost-only; built-in multipart correctness | n |
| `client_timestamp` | Integer unix seconds | Server only logs it | n |

**Open questions:** none - all resolved or logged above.

**Implicit-requirement dimensions sweep:** auth/rate limits N/A (single-user localhost,
§2/§8); idempotency N/A (one-shot POST, no HTTP retry — retry exists only for the
clipboard write, §4.3); data lifecycle — audio held in memory, dropped after the request,
no disk persistence (cap bound above); observability — client logs to a single appended
log file (truncate on start) + server-side logs are the diagnostic source (§4.1);
state-transition integrity — guard table (CLI-01/02/03/04); concurrency/ordering — one
recording at a time, taps during Processing ignored, a single mpsc channel serializes
hotkey events; input validation — WAV bytes produced by our own writer, zero-byte
recording rejected (CLI-09), response JSON validated (CLI-14); failure/partial-failure —
server down, non-2xx, malformed JSON, clipboard lock, missing input device all land on the
generic error notice; external-dependency failure — tray/hotkey registration failure
surfaces an error toast at startup, device absence at recording time surfaces the generic
error.

---

## User Stories

### P1: State machine — "Model the flow, guard the transitions" ⭐ MVP

**User Story**: As a user, I tap the global hotkey to start recording, tap again to
commit, and the client walks a strict `Idle → Recording → Processing → Idle` cycle so the
flow can never double-record or drop a stop (§4).

**Why P1**: The core of the whole product; everything else hangs off it.

**Acceptance Criteria**:

1. CLI-01 The client core SHALL expose a state machine with exactly the states `Idle`, `Recording`, and `Processing` and allow only the transitions `Idle→Recording`, `Recording→Processing`, and `Processing→Idle`.
2. CLI-02 WHEN the hotkey is pressed WHILE the core is `Recording` THEN the core SHALL stop the recording and transition to `Processing`.
3. CLI-03 WHEN the hotkey is pressed WHILE the core is `Processing` THEN the core SHALL ignore the event and stay in `Processing`.
4. CLI-04 The client SHALL never run more than one recording at a time.

**Independent Test**: Drive event sequences through the core with a recorder/processor
injected; assert the state after each event and that double-taps or taps during
Processing are rejected.

---

### P1: Non-blocking processing — "Background work, no freeze" ⭐ MVP

**User Story**: As a user, after I tap to commit I immediately go back to my prior window
and keep working while the request flies to the server (§4.1 step 4, §7).

**Why P1**: §4.1 explicitly guarantees the user is not blocked.

**Acceptance Criteria**:

1. CLI-05 WHEN the core transitions to `Processing` THEN the `/process` request SHALL be dispatched without blocking the state machine (the transition returns before the HTTP result arrives).

**Independent Test**: Inject a processor that blocks on a channel; call the transition;
assert the call returns before the injected processor completes.

---

### P1: The three visual states — "Know what it's doing" ⭐ MVP

**User Story**: As a user, I can read at a glance whether the client is Recording,
Processing, or done from the tray (§4.2).

**Why P1**: §4.2 requires exactly three explicit visual states.

**Acceptance Criteria**:

1. CLI-06 WHILE the client is `Recording` the tray tooltip SHALL read `Recording…`.
2. CLI-07 WHILE the client is `Processing` the tray tooltip SHALL read `Processing…`.

**Independent Test**: The pure mapping of core state → tooltip label is unit-tested on
Linux; the tray glue consumes that label (Windows type-check / manual smoke).

---

### P1: Recording → WAV — "Capture the voice" ⭐ MVP

**User Story**: As a user, everything I say between my two taps arrives at the server as a
standard WAV, no extra steps (§4.1 steps 2-3, §6.1).

**Why P1**: The capture half of the loop; goes straight over `/process`.

**Acceptance Criteria**:

1. CLI-08 WHEN a recording completes THEN the client SHALL produce a WAV byte stream (RIFF header + PCM samples) ready to send as the multipart `audio_file`.
2. CLI-09 IF a recording captures zero audio bytes THEN the client SHALL treat the recording as failed, show the generic error notice, and SHALL NOT make an HTTP request.
3. CLI-10 IF a recording reaches the 300s cap THEN the client SHALL stop it and process it exactly like a manual hotkey stop.

**Independent Test**: The WAV writer is asserted byte-for-byte (RIFF/WAVE/fmt headers,
sample rate, block alignment) on Linux; the cap path is unit-tested with an injected clock;
the zero-byte path is unit-tested with an empty capture.

---

### P1: The HTTP boundary — "Talks to the server, exactly per spec" ⭐ MVP

**User Story**: As a user, my recording and the `pt` metadata go to the server via the
single defined boundary and the answer lands where it belongs (§6).

**Why P1**: The client-server contract is the whole integration; §6 is precise about it.

**Acceptance Criteria**:

1. CLI-11 WHEN the client sends a recording THEN it SHALL `POST` `multipart/form-data` to `{endpoint}/process` with fields `audio_file` (the WAV bytes) and `metadata` (a JSON string containing `language: "pt"` and `client_timestamp`).
2. CLI-12 The client's endpoint SHALL default to `http://127.0.0.1:8000` and SHALL be overridable via the `X9AI_SERVER_URL` environment variable.
3. CLI-13 WHEN the server responds with HTTP 2xx and JSON `{"status": "success", "text": ..., "processing_time_ms": ...}` THEN the client SHALL write `text` to the clipboard.
4. CLI-14 IF the server responds with a non-2xx status, a JSON `status` of `"error"`, malformed JSON, a connection failure, or a request timeout THEN the client SHALL show the generic error notice "Falha no processamento. Verifique a conexão com o servidor." and SHALL NOT write the clipboard.

**Independent Test**: A stub TCP listener asserts the multipart structure (two fields,
correct boundary, `audio_file` = WAV bytes, `metadata` JSON decodes) and returns canned
success/error bodies; response parsing is unit-tested against exact JSON fixtures; the
endpoint override is asserted from `X9AI_SERVER_URL`.

---

### P1: Clipboard reliability — "Survive OS lock contention" ⭐ MVP

**User Story**: As a user, even if another app briefly holds the clipboard, my text still
lands there (§4.3).

**Why P1**: §4.3/AD-006 mandate the exact retry contract.

**Acceptance Criteria**:

1. CLI-15 WHEN the client writes the clipboard THEN it SHALL attempt the write up to 3 times with a 50ms delay between attempts.
2. CLI-16 IF all 3 clipboard write attempts fail THEN the client SHALL show the generic error notice.

**Independent Test**: Inject a clipboard sink that fails N times then succeeds; assert
attempt count and 50ms delays (recorded by an injected sleeper); assert the generic error
fires only when attempt 3 fails.

---

### P1: Final notification — "One subtle toast at the end" ⭐ MVP

**User Story**: As a user, when the loop finishes I get one quiet toast telling me where I
am, then I paste (§4.1 step 5).

**Why P1**: The "Success or Error" visual resolution of §4.1/§4.2.

**Acceptance Criteria**:

1. CLI-17 WHEN the client reaches Success THEN it SHALL pop an OS notification reading "Pronto para colar!".
2. CLI-18 WHEN the client reaches Error THEN it SHALL pop an OS notification reading "Falha no processamento. Verifique a conexão com o servidor.".

**Independent Test**: The notify call argument for each outcome is asserted via an
injected notifier on Linux; the `Shell_NotifyIcon` balloon is glue (Windows
type-check / manual smoke).

---

## Edge Cases

- IF the tray/hotkey registration fails at startup THEN the client SHALL pop the generic error notice and exit.
- IF hotkey while `Processing` THEN ignore (CLI-03).
- IF no input device exists at record start THEN the client SHALL show the generic error notice and return to `Idle` without an HTTP request.
- IF a recording reaches 300s THEN auto-stop and process (CLI-10).
- IF the server returns success with empty `text` THEN the client still writes the (empty) clipboard (assumption).
- IF the recorded WAV is within 50 MB (always, given the 300s cap) THEN no client-side size rejection is needed; server enforces `max_audio_bytes`.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| CLI-01 | P1: State machine | Tasks | Pending |
| CLI-02 | P1: State machine | Tasks | Pending |
| CLI-03 | P1: State machine | Tasks | Pending |
| CLI-04 | P1: State machine | Tasks | Pending |
| CLI-05 | P1: Non-blocking processing | Tasks | Pending |
| CLI-06 | P1: Visual states | Tasks | Pending |
| CLI-07 | P1: Visual states | Tasks | Pending |
| CLI-08 | P1: Recording → WAV | Tasks | Pending |
| CLI-09 | P1: Recording → WAV | Tasks | Pending |
| CLI-10 | P1: Recording → WAV | Tasks | Pending |
| CLI-11 | P1: HTTP boundary | Tasks | Pending |
| CLI-12 | P1: HTTP boundary | Tasks | Pending |
| CLI-13 | P1: HTTP boundary | Tasks | Pending |
| CLI-14 | P1: HTTP boundary | Tasks | Pending |
| CLI-15 | P1: Clipboard reliability | Tasks | Pending |
| CLI-16 | P1: Clipboard reliability | Tasks | Pending |
| CLI-17 | P1: Final notification | Tasks | Pending |
| CLI-18 | P1: Final notification | Tasks | Pending |

**Coverage:** 18 total, 18 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] Core unit tests on Linux green: state machine transitions + guards, WAV header bytes, multipart structure asserted by a stub listener, success/error/malformed response parsing, clipboard 3×50ms retry with injected sleeper, generic-error mapping on every failure path, non-blocking dispatch, tooltip label mapping
- [ ] Crate compiles and tests build on Linux (Windows glue stubbed `main`) and, where the toolchain permits, `cargo check --target x86_64-pc-windows-gnu` type-checks the glue module
- [ ] Full Windows build + manual loop smoke (tray shows states, hotkey captures, clipboard lands, toasts pop) documented as a post-merge manual step on a Windows host (AD-010)