# X9AI — Agent Guide

## Project

X9AI is a **single-user, Windows-only** personal tool that captures spoken brain-dumps and
puts clean, ready-to-paste text directly on the clipboard.

- **Client:** Rust. System-tray utility, global hotkey, silent background. Thin wrapper:
  record audio → `POST /process` → write clipboard (retry up to 3× at 50ms).
- **Server:** Python + FastAPI. Local Whisper (PT-BR) transcription + normalization pass.
  Single HTTP boundary: `POST /process` (multipart), JSON response.
- **Language:** PT-BR primary, English secondary.

The durable contract is `docs/spec.md` — it is the sole source of truth that the client,
server, and test harness all implement against. Before changing behavior, read it.

## Workflow (Spec-Driven)

Use the **`tlc-spec-driven`** skill (installed at `.opencode/skills/tlc-spec-driven/`) for
all feature planning and implementation. It runs four adaptive phases as needed —
**Specify → Design → Tasks → Execute** — sized to the feature's complexity, and enforces
verification with shipped scripts in the skill's own `scripts/` dir.

Follow its conventions and invariants:

- **Plan/invariant memory lives in `.specs/`** (`STATE.md` decisions + handoff,
  `features/<feature>/{spec,design,tasks,validation}.md`). Create files lazily per phase.
- **Everything traces to `docs/spec.md`.** New features either extend the spec or reference
  it; acceptance criteria are written against spec-defined outcomes, never the implementation.
- **Gates are code, not memory.** Run the skill's validators before confirming work:
  `validate_spec.py`, `validate_tasks.py`, `check_commit.py`, `validate_state.py`.
- **Commits are atomic and Conventional Commits** — one commit per task.
- **The golden-corpus oracle** (`docs/spec.md` §9) is the test harness: ≥90% semantic
  similarity, structural checks, keyword presence. Do not weaken or delete these tests.
- **Blast radius:** approving local work authorizes local commits only. `git push`, deploy,
  or any remote/destructive operation requires explicit go-ahead for that action.

## Stack Invariants

- Rust client: self-contained portable exe, no .NET/Electron, minimal memory footprint.
- Server seam: cloud vs local transcription is a complete swap across the `POST /process`
  boundary; never maintain both in parallel.
- No auth, no multi-tenant, no streaming in v1 (see `docs/spec.md` §2, §7, §8).
