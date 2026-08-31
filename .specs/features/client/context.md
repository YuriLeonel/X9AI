# client Context

**Gathered:** 2026-08-30
**Spec:** `.specs/features/client/spec.md`
**Status:** Ready for design

---

## Feature Boundary

Build the Rust client behind the single `POST /process` HTTP boundary (`docs/spec.md`
§3.1, §4, §6, §7). Platform-agnostic core (state machine, WAV writer, multipart builder,
response parser, clipboard-retry policy, error mapping, UI-state rendering) is unit-tested
on Linux (AD-010); the Windows glue (system tray, global hotkey, cpal recording, arboard
clipboard, winrt toasts) is `cfg(windows)`-gated and built/type-checked per AD-010.

---

## Implementation Decisions

### Windows glue crate stack (user decision)

- **tray-icon** — system tray icon + menu + tooltip (the sole UI surface).
- **global-hotkey** — registers the global hotkey (`Ctrl+Alt+Space`).
- **cpal** — default input device capture (WASAPI).
- **arboard** — clipboard write (implements the core `ClipboardSink` trait).
- **Classic tray balloon** — final Success/Error notification: `Shell_NotifyIcon`
  `NIF_INFO` balloon from our own hidden message-pump window (user decision, replacing
  winrt-notification). Research found WinRT toasts require an AUMID Start-menu shortcut
  for a portable exe, which the balloon avoids; Win11 may suppress legacy balloons —
  logged in design Risks & Concerns with UAT verification + a toasts-with-AUMID
  follow-up contingency.
- All Windows deps are `[target.'cfg(windows)'.dependencies]`; the glue module is
  `#[cfg(target_os = "windows")]`, so Linux `cargo build`/`cargo test` exercises the core
  and compiles a stub `main` that reports "Windows-only".

### Visual states (user decision)

- Recording / Processing are shown by the tray icon tooltip text; the final result pops a
  single OS toast (Success or Error). No per-state toasts, no focus-stealing windows
  (§4.1 "subtle notification", §4.2 three explicit states).

### Server endpoint config (user decision)

- Default `http://127.0.0.1:8000`, overridable via `X9AI_SERVER_URL`. No config file in
  v1 (single user, localhost only).

### Autostart (user decision)

- **P2 — deferred past MVP** (§3.1 lists it, but the core loop is the deliverable). Moved
  to Out of Scope for this feature.

### Core/glue seam (AD-010)

- Effect traits for the core so Linux gates are deterministic and Windows-free:
  `ClipboardSink` (arboard impl), `Recorder` (cpal impl), `Notifier` (winrt impl),
  `Clock`/`Sleeper` (std impls; fakes in tests for the 50ms retry delays).
- The core drives a `UiState` (Recording/Processing/Idle labels) that the tray tooltip
  renders; the mapping is pure and unit-testable on Linux.

### Recording parameters (agent decision, flagged in spec)

- Request 16-bit PCM mono 16 kHz from the default input; on device rejection fall back to
  the device default config and write the WAV at the true sample rate (faster-whisper
  resamples internally via slower PyAV/ffmpeg decode). Spec §6.1 says client-standardized
  `.wav`; the H/WAV header carries the true rate either way.
- Hard cap 300s: auto-stop and process, keeping a runaway recording from crossing the
  server's 50 MB `max_audio_bytes` (44.1 kHz mono i16 ≈ 88 KB/s → ~9.5 min; 16 kHz ≈
  32 KB/s → ~25 min). Distinct from §8's excluded silence detection.
- Metadata: `{"language": "pt", "client_timestamp": <epoch seconds at record start>}`.

### Runtime dependencies (agent decision)

- HTTP: `reqwest` (blocking) with `default-features = false` + `multipart` + `json` — no
  TLS stack, localhost-only. Multipart built via `reqwest::multipart::Form` (correct
  boundary handling), asserted in tests by re-parsing on a stub listener.
- `serde`/`serde_json` for response parsing. `std::time` for the timestamp. No other
  runtime deps in core.

### Messages language

- User-facing notifications in PT-BR (§2 primary), the spec §4.1 English strings are
  illustrative:
  - Success: "Pronto para colar!"
  - Error: "Falha no processamento. Verifique a conexão com o servidor."

### Windows verification proxy

- On Linux: `cargo test` (core) + `cargo check --target x86_64-pc-windows-gnu` (glue
  type-check) if the rustup target imports cleanly; otherwise the full Windows build +
  manual smoke is a documented post-merge step (AD-010), mirroring the oracle's real-clip
  pre-UAT step.

### Agent's Discretion

- Exact icon bytes/resolution for `tray-icon::Icon::from_rgba`.
- Tray menu items: "Sair" (Exit) always; "Parar gravação" (Stop recording) only while
  Recording — the hotkey-lost fallback.
- Threading: hotkey WM events dispatched over an mpsc channel into one thread that owns
  the tray + state machine; recording runs on its own thread with cpal's callback
  feeding PCM into the core WAV writer; the HTTP request runs on a worker thread.

### Declined / Undiscussed Gray Areas → Assumptions

- Hotkey fixed to `Ctrl+Alt+Space` in v1 (no rebind UI); registration failure surfaces an
  error toast at startup (assumption).
- Success with empty `text` still writes the clipboard (assumption; silence detection is
  §8 out of scope).

---

## Specific References

- `docs/spec.md` §3.1 (Rust client, tray, portable exe, autostart), §4 (state machine +
  flow), §4.2 (UI states), §4.3 (clipboard retry 3×50ms), §6 (HTTP contract), §7
  (batch-after-stop, latency ≤5s acceptable).
- `server/x9ai/app.py` — multipart field names (`audio_file`, `metadata`), error mapping,
  `language` default `pt`, `client_timestamp` for logging.
- `server/x9ai/schemas.py` — success/error response JSON shape.
- `server/x9ai/transcriber.py` — audio bytes go straight to faster-whisper (decode-time
  resampling), so WAV at device rate is safe.

---

## Deferred Ideas

- Autostart with Windows (§3.1): registry tweak, deferred to post-MVP (P2).
- Hotkey rebinding UI / multiple hotkeys.
- Config file in `%APPDATA%` (endpoint, recording, hotkey): env-override suffices for a
  single-user tool; revisit if settings multiply.