# X9AI — Product Specification (v1)

Captured via grilling session. This document is the durable contract that both the
client and server (and the test harness) implement against.

---

## 1. Vision — The Tools Philosophy

**X9AI** is a frictionless personal tool that captures spoken brain-dumps and instantly
transforms them into structured, ready-to-use text directly on the clipboard.

- **Domain:** Personal productivity, rapid knowledge capture, thought organization.
- **Mechanism:** A one-tap global-hotkey native client records audio and pipes it through
  a highly accurate transcription model (Whisper) optimized for speed.
- **Outcome:** Eliminates the cognitive load and physical friction of typing, turning raw
  spoken thoughts into instantly usable text wherever the user is working.

**AI is the product.** The application wrapper is a delivery mechanism. The core value is
the accuracy, speed, and automatic formatting provided by the AI pipeline. If the AI is
removed or slow, the product fails its purpose. Business rules and architecture prioritize
the speed and reliability of this AI output above all else.

---

## 2. Scope & Platforms

- **Target (v1):** Windows desktop only.
- **Explicitly out of scope for v1:** Android / mobile. (Foreground-service limits and
  scoped clipboard access would severely slow validation of the core loop.)
- **Target audience:** Strictly personal, single-tenant. The only user. No auth, no scaling.
- **Source language (v1):** Brazilian Portuguese (PT-BR) primary, English secondary.
  Body of the golden corpus, structural checks, and filler blacklist are PT-BR.

---

## 3. Architecture

A thin OS-native **client** (Windows) and a detached **server** (processing microservice),
communicating over a single HTTP boundary: `POST /process`.

The client is a "dumb" wrapper: global hotkey, audio recording, HTTP request, clipboard
write, minimal status UI. It knows nothing about transcription or normalization.

Where/how the server runs (WSL, Docker, native Python) is strictly a development/deployment
concern, NOT an architectural constraint of the client. The endpoint is `localhost`.

```
[Windows Client]  --HTTP POST /process (multipart)-->  [Processing Server]
[  C# / .NET or Rust  ]        <-- JSON response ---   [Python / FastAPI]
```

### 3.1 Client

- Language: **Rust** (decided). Self-contained portable executable, no .NET runtime
  dependency, lowest background memory footprint, and no GC pauses — guaranteeing
  consistently instant, frictionless global hotkey interception.
  Heavy web-wrappers (Electron) are disqualified for this system-tray utility context.
- Lives in the **system tray**, runs silently in the background.
- **Packaging:** portable executable for v1 (no installer overhead).
- **Autostart:** basic setting to autostart with Windows.

### 3.2 Server

- Lightweight Python microservice (**FastAPI**) to natively interface with ML libraries
  (Whisper, transformers).
- Two-step NLP pipeline (see §5).

---

## 4. Client State Machine & User Flow

Single global hotkey toggles. Sequential, non-blocking, automatic clipboard injection.

```
Idle -> [Tap] -> Recording -> [Tap] -> Processing -> (Success | Error) -> Idle
```

### 4.1 Flow

1. App runs silently in system tray.
2. User taps the global hotkey → **Recording** begins.
3. User speaks, taps the hotkey again → **Processing** begins (stops recording).
4. Client fires the HTTP request and enters background **Processing** state.
   User immediately returns to their prior window and continues working (non-blocking).
5. On HTTP response:
   - **Success:** client automatically writes text to clipboard (with retry), then pops a
     subtle OS notification (e.g., "Ready to paste!").
   - **Error:** client pops a friendly, generic fallback message
     (e.g., "Processing failed. Check server connection."). Detailed logs/diagnostics
     live on the server only.

### 4.2 UI States

Three explicit visual states are required:
- **Recording**
- **Processing...**
- Final notification (**Success** or **Error**)

### 4.3 Reliability — Clipboard write

To survive transient OS locks (another app reading the clipboard), the client MUST retry
the clipboard write: **up to 3 attempts with a 50ms delay between attempts.**

---

## 5. The NLP Pipeline (Server-side)

Two-step processing:

1. **Transcription:** audio → raw text (Whisper). Local model, targeting medium/large tier
   depending on hardware. Must be highly proficient in PT-BR.
2. **Normalization:** raw text → clean text. A lightweight pass to fix grammar, remove
   filler words, and ensure perfect punctuation and casing (PT-BR). The output must require
   **zero manual editing** before send/save.

**Target environment decision:** Transcription runs **locally** for v1 (privacy, zero cost).

**Swappability:** The seam is a single combined interface. Migration to a cloud API is a
*complete swap* — both environments will NOT be maintained in parallel (avoid dead code).
The client does not care whether the endpoint is a local Python script or an external cloud
API (future: cost-effective Chinese LLM/API for higher quality, prioritizing PT-BR
instruction following). The boundary is the HTTP request itself.

---

## 6. The HTTP Contract

### 6.1 Request — `POST /process`

`multipart/form-data` containing:

| Field | Type | Description |
|-------|------|-------------|
| `audio_file` | file bytes | Raw recording, standardized by the client (e.g., `.wav`). |
| `metadata` | string (JSON-in-string) | `{"language": "pt", "client_timestamp": 1715000000}` — future routing/debugging. |

### 6.2 Response — JSON

**Success:**
```json
{ "status": "success", "text": "<normalized text>", "processing_time_ms": 1450 }
```

**Error:**
```json
{ "status": "error", "message": "<generic error string mapped by the server>" }
```

---

## 7. Performance Requirements

- **Flow:** batch after stop (record-then-process). No streaming/overlap in v1 — overlap
  adds complexity and can degrade context-aware punctuation.
- **Latency budget (stop → paste):** ≥ 5 seconds is acceptable. Accuracy and quality are
  prioritized over speed.

---

## 8. Deferred Items (explicitly out of scope for v1)

- All adversarial failure modes (silence/timeout/network drop) beyond the single generic
  error message + server-side logging. Happy path is assumed to validate the core loop.
- Android / mobile.
- Authtication / multi-tenant.
- Streaming transcription.
- Task/email auto-structuring (raw→clean only, not raw→restructured).

---

## 9. Verification & The Oracle (Test Harness)

AI output is non-deterministic, so testing is **not** byte-for-byte string comparison.
Use a **golden-transcript corpus**: a small set of pre-recorded PT-BR test audio files with
known expected golden text.

A **v1 PASS** requires the entire golden-transcript corpus to pass:

### 9.1 Semantic Similarity (primary)
Using a standard embedding model (e.g., cosine similarity), the output must achieve
**≥ 90% similarity** to the golden text. Ensures core meaning is preserved even if
synonyms are swapped.

### 9.2 Structural Checks (normalization proof)
Regex/heuristic assertions:
- Sentences start with a capital letter and end with proper punctuation.
- Blacklist confirms absence of common PT-BR filler words:
  **"tipo", "né", "então", "ééé"** (and English: "um", "uh").

### 9.3 Keyword Presence (fallback)
Crucial nouns/verbs from the golden text must be present.

---

## 10. Component Decision Summary

| Concern | Decision |
|---------|----------|
| Client language | **Rust** (portable, self-contained, no GC, minimal footprint) |
| Server | Python + FastAPI |
| Transcription | Whisper, local, medium/large tier, PT-BR proficient |
| Normalization | Lightweight local pass (Whisper prompting or small local LLM) |
| UI delivery | System tray, silent background, portable exe |
| Client-server | Single `POST /process` HTTP boundary over localhost |
| Language | PT-BR primary, English secondary |
| Clipboard reliability | Retry up to 3× at 50ms |
| Goal state | Spec-driven development, AI-first, strong test harness |
