# X9AI

A frictionless personal tool that captures spoken brain-dumps and instantly turns them
into clean, ready-to-paste text — dropped straight onto your clipboard.

Speak your thoughts. One hotkey tap to start, one to stop. X9AI transcribes
(local Whisper, PT-BR) and normalizes the text, then writes it to the clipboard so what
you said is immediately pastable, requiring **zero manual editing**.

> The durable contract is [`docs/spec.md`](docs/spec.md). Any feature, test, or behavior
> in this repository implements against it.

---

## How it works

```
Idle -> [Tap] -> Recording -> [Tap] -> Processing -> (Success | Error) -> Idle
```

A thin, silent, system-tray **client** (Rust) rides a global hotkey. It is a "dumb"
wrapper: it records audio, POSTs it, and writes the response to the clipboard (with up to
3 retries at 50ms to survive transient OS locks). It knows nothing about transcription or
normalization.

```
[ Rust Client (Windows, system tray) ]  --HTTP POST /process (multipart)-->  [ Server ]
[  clipboard write + notification                     <-- JSON response ---  [FastAPI]
```

The **server** is a lightweight Python/FastAPI microservice that runs a two-step NLP
pipeline:

1. **Transcription** — audio → raw text, local Whisper model, PT-BR proficient.
2. **Normalization** — raw text → clean text: grammar, removal of filler words
   (`tipo`, `né`, `então`, …), and proper punctuation and casing.

The two communicate over a single HTTP boundary, `POST /process`
([§6 of the spec](docs/spec.md#6-the-http-contract)). Swapping local transcription for a
cloud API is a complete swap at that boundary — never both in parallel.

## What's implemented

- `server-api` — the FastAPI `POST /process` boundary: request validation, error mapping
  (400/413/500), structured per-request logging, timing, and the `Pipeline` seam with a
  deterministic stub. 31 tests, spec-validated.
- Next in the roadmap: `nlp-pipeline` (real Whisper transcription + normalization),
  `golden-oracle` (the golden-corpus harness), `client` (Rust).

## Repository layout

```
docs/spec.md        The product contract (v1)
.specs/             Spec-driven feature artifacts (decisions, specs, tasks, validation)
server/             Python + FastAPI processing server
  x9ai/             app (HTTP boundary), pipeline seam, schemas, config, logging
  tests/            31 pytest tests against docs/spec.md §6
client/             (not yet built) Rust system-tray client
```

## Running the server (dev)

```bash
cd server
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn x9ai.app:create_app --factory --host 127.0.0.1 --port 8000
```

The current build serves the stub pipeline (`stub:<language>:<bytes>`), so `POST /process`
contracts can be exercised end-to-end before the real transcription lands.

```bash
curl -s -F audio_file=@/tmp/sample.wav -F 'metadata={"language":"pt"}' \
  http://127.0.0.1:8000/process
# → {"status":"success","text":"stub:pt:88244","processing_time_ms":0}
```

Tests:

```bash
cd server && .venv/bin/python -m pytest -q && .venv/bin/ruff check .
```

## Development

Spec-driven, test-first development: each feature goes through
Specify → Design → Tasks → Execute → independent verification, lands in a dedicated
branch, and is merged to `main` with atomic Conventional Commits (one commit per task).
Roadmap and decisions live in [`.specs/STATE.md`](.specs/STATE.md).

## License

Private. Single-user personal tool — the only user is you.