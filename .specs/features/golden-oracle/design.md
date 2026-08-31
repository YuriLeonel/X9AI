# golden-oracle Design

**Spec**: `.specs/features/golden-oracle/spec.md`
**Status**: Draft

---

## Architecture Overview

The oracle is a leaf module on the server package: a scoring library, a corpus loader
and runner, plus a `python -m x9ai.oracle run` CLI. It reuses the shipped seams
(`Pipeline`/`RealPipeline`, `RuleBasedNormalizer.FILLERS`, `Settings`) and follows the
established lazy-extras pattern (AD-011: import must not fail without the extra, only the
real call raises). Semantic similarity runs through an `EmbeddingProvider` protocol whose
only shipped implementation lazily loads sentence-transformers; deterministic gates inject
a test fake, exactly like `model_factory` in the transcriber.

```mermaid
graph TD
    CLI[python -m x9ai.oracle run DIR] --> Load[load_corpus golden.json -> Entry list]
    Load --> Run[run_corpus entries, pipeline, embedder]
    Run -->|audio bytes + language| P[Pipeline seam -> RealPipeline]
    P --> T[WhisperTranscriber*]
    P --> N[RuleBasedNormalizer]
    Run --> E[SemanticEmbedder*]
    E -. FakeEmbedder injected in gates .-> Proto[EmbeddingProvider protocol]
    Run --> Score[cosine >= 0.90 AND structural AND keywords]
    Score --> Rep[EntryOutcome per entry]
    Rep --> Verdict[CorpusReport + exit 0/1]
    * lazy import; absent extra = only the call raises
```

**Approach exploration. Two viable shapes; Approach A chosen.**

- **A — Flat `x9ai/oracle.py` module** (chosen): one cohesive harness module holding the
  provider protocol, real embedder, scoring, corpus loader, runner, report types, and the
  `if __name__ == "__main__"` CLI. `python -m x9ai.oracle run <dir>` works out of the box.
  Matches the flat-module precedent set in `nlp-pipeline` (Approach A there, which rejected
  a `nlp/` subpackage as excess structure); single cohesive role = "the oracle harness".
- **B — `x9ai/oracle/` package** (`embedding.py`, `checks.py`, `corpus.py`, `runner.py`,
  `__main__.py`): finer module separation but adds a package boundary the codebase
  convention explicitly declined (see `nlp-pipeline/design.md` "Approach B rejected") and
  forces a `pyproject` `packages` update. Rejected for consistency.
- **C — pytest-plugin-only harness**: no CLI; already rejected by the user (spec assumed
  the CLI surface, AS-GO-15).

## Code Reuse Analysis

### Existing Components to Leverage

| Component | Location | How to Use |
| --------- | -------- | ---------- |
| `RuleBasedNormalizer.FILLERS` | `server/x9ai/normalizer.py:31` | Single source of truth for the filler blacklist (GO-08); oracle builds its regex from this tuple, never duplicates it |
| `Pipeline` / `RealPipeline` | `server/x9ai/pipeline.py` | `run_corpus` consumes a `Pipeline`; CLI builds `RealPipeline(WhisperTranscriber(settings), RuleBasedNormalizer())` |
| `WhisperTranscriber` | `server/x9ai/transcriber.py` | Lazy faster-whisper; reused as-is for the CLI's real-clip run |
| `Settings` + `Settings.from_env()` | `server/x9ai/config.py` | Extend with `embedding_model` (reads `ORACLE_EMBEDDING_MODEL`); CLI builds settings from env |
| Lazy-extras pattern | `server/x9ai/transcriber.py:18-25` | Mirror for `SemanticEmbedder`: import inside the call, never at module scope (GO-03) |
| `pyproject` extras | `server/pyproject.toml:16-24` | Add `oracle = ["sentence-transformers>=2.2"]` beside `whisper` / `dev` |

### Integration Points

| System | Integration Method |
| ------ | ------------------ |
| HTTP layer | none — the oracle is a dev/validation tool, not part of `POST /process` |
| `RealPipeline` | CLI default; tests inject a fake pipeline (mock mode) |
| sentence-transformers | lazy import inside `SemanticEmbedder.encode`; model name from `Settings.embedding_model` |
| `docs/spec.md` §9 | thresholds/blacklist implemented as constants sourced from the spec: `SIMILARITY_THRESHOLD = 0.90`, `FILLERS` reused |

---

## Components

### `x9ai/oracle.py` — the oracle harness (library + CLI)

- **Purpose**: Score pipeline output against a golden corpus (§9) and drive real clip runs.
- **Location**: `server/x9ai/oracle.py`
- **Interfaces**:
  - `SIMILARITY_THRESHOLD: float = 0.90`
  - `class EmbeddingProvider(Protocol)`: `encode(texts: list[str]) -> list[list[float]]`
  - `def cosine(a: list[float], b: list[float]) -> float` — pure-Python; zero-vector → `0.0`
  - `class SemanticEmbedder(EmbeddingProvider)`: `__init__(settings: Settings | None = None)`; lazily imports `SentenceTransformer` inside `encode`, caches the model, reads `settings.embedding_model`; returns `list[list[float]]`
  - `@dataclass StructuralOutcome`: `capital_start` / `ending_punctuation` / `no_fillers` booleans + `passed` property (all three)
  - `def structural_check(output: str) -> StructuralOutcome` — sentence split on `[.!?]`, first-char uppercase, tail must end with `.!?`, filler regex from `RuleBasedNormalizer.FILLERS`
  - `def keywords_present(keywords: Sequence[str], output: str) -> bool` — case-insensitive substring; empty `keywords` → `True` (GO-11)
  - `@dataclass ScoreResult`: `similarity`, `semantic_passed`, `structural: StructuralOutcome`, `keywords_passed`, `passed` (conjunction, GO-14)
  - `def score(golden: str, output: str, embedder: EmbeddingProvider) -> ScoreResult` — cosine of embedded golden vs output; semantic = `similarity >= SIMILARITY_THRESHOLD`
  - `@dataclass Entry`: `id`, `audio: Path` (resolved absolute), `language="pt"`, `golden`, `keywords: tuple[str, ...] = ()`
  - `@dataclass EntryOutcome`: `entry_id`, `passed`, `similarity: float | None`, `structural: StructuralOutcome | None`, `keywords_passed: bool | None`, `error: str | None`
  - `@dataclass CorpusReport`: `outcomes: tuple[EntryOutcome, ...]`, `passed` property = all outcomes pass
  - `def load_corpus(corpus_dir: str | Path) -> list[Entry]` — reads `golden.json`, validates, resolves audio paths; raises `CorpusError` on malformed manifest
  - `def run_corpus(entries, pipeline: Pipeline, embedder: EmbeddingProvider) -> CorpusReport` — per-entry: missing audio → FAILED; only `pipeline.process` is error-guarded (per-entry FAILED, continue, GO-16); empty output → FAILED (GO-09); else score
  - `def main(argv: list[str] | None = None) -> int` — argparse `run <corpus-dir>`; builds `RealPipeline(WhisperTranscriber(settings), RuleBasedNormalizer())` + `SemanticEmbedder(settings)` from `Settings.from_env()`; prints report; `0` pass / `1` fail / `2` load-or-extra error
  - `if __name__ == "__main__": raise SystemExit(main())`
- **Dependencies**: `argparse`, `json`, `math`, `re`, `dataclasses`, `abc`, `os`; `x9ai.config.Settings`, `x9ai.normalizer.RuleBasedNormalizer`, `x9ai.transcriber.WhisperTranscriber`, `x9ai.pipeline.Pipeline/RealPipeline`; sentence-transformers is a **lazy import**.
- **Reuses**: all seams/constants above; the lazy-extra pattern; `Settings.from_env`.

### `x9ai/config.py` — embedding settings (extend)

- **Purpose**: Env-configurable oracle model name (GO-02).
- **Interfaces**: add `embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"`; `from_env()` reads `ORACLE_EMBEDDING_MODEL` via `_env_str`.
- **Reuses**: frozen `Settings` + `_env_str`.

### `server/pyproject.toml` — oracle extra (extend)

- **Purpose**: `[oracle]` extra installs sentence-transformers; absent in lean/dev envs (GO-03).
- **Interfaces**: `oracle = ["sentence-transformers>=2.2"]`; `packages` unchanged (flat module).
- **Reuses**: existing extras block.

### `server/tests/test_oracle_scoring.py` — semantic/structural/keyword ACs

- GO-01..05 (FakeEmbedder + cosine + threshold), GO-06..09 (structural), GO-10..11 (keywords), GO-03 (module imports without `[oracle]`).
- `FakeEmbedder` (test local): hash-based deterministic vectors + manual override dict for exact cosine control (e.g., 1.0, 0.90 boundary, 0.0).

### `server/tests/test_oracle_runner.py` — corpus/runner/CLI ACs

- GO-12..16: load_corpus schema + missing audio + malformed manifest abort + pipeline-raise continuation + empty output FAILED + mock-mode determinism (two runs, byte-identical reports) + CLI exit codes via `main()` and one subprocess check.

---

## Data Models (if applicable)

### Corpus manifest — `golden.json`

```json
{
  "entries": [
    {
      "id": "pt-demo-01",
      "audio": "clips/pt-demo-01.wav",
      "language": "pt",
      "golden": "O aniversário foi ontem no parque.",
      "keywords": ["aniversário", "parque"]
    }
  ]
}
```

**Rules**: top-level object with `entries` array; each entry requires non-empty `id`,
`audio`, non-empty `golden`; `language` defaults `"pt"`; `keywords` is an optional array
of strings (defaults empty). Validation errors raise `CorpusError` naming the entry.

### In-memory flow

`golden.json` → `list[Entry]` → per entry: `audio bytes` → `pipeline.process` → `output str`
→ `ScoreResult` (similarity, structural, keywords) → `EntryOutcome` → `CorpusReport`.

---

## Error Handling Strategy

| Error Scenario | Handling | User Impact |
| -------------- | -------- | ----------- |
| `[oracle]` extra missing (encode raises `ImportError`) | Propagates out of `run_corpus` (guarded scope is only `pipeline.process`); CLI catches → friendly "install x9ai-server[oracle]" message, exit 2 | Clear actionable message |
| `[whisper]` extra missing (transcribe raises `ImportError`) | Same as above (inside guard) — but forces per-entry FAILED; CLI message covers both extras | Every entry reported FAILED with the import error |
| Model download / load failure (first encode) | Propagates → CLI exit 2 with message | No silent partial run |
| Pipeline raises mid-entry | Caught in `run_corpus`, recorded `error`, entry FAILED, continue (GO-16) | One bad clip doesn't mask the rest |
| Missing audio file | Entry FAILED with `"audio file not found: <path>"`, continue | Visible in report |
| Empty/whitespace output | Entry FAILED `"empty output"`, before scoring (GO-09) | Explicit, no NaN cosines |
| Malformed / missing `golden.json` | `load_corpus` raises `CorpusError`; CLI prints it, exit 2 | Abort, no silent partial run |

---

## Risks & Concerns

| Concern | Location (file:line) | Impact | Mitigation |
| ------- | -------------------- | ------ | ---------- |
| Sentence-split heuristic false-passes unterminated tails | `oracle.py` structural | Output "A. tail" passes | `ending_punctuation` requires the full output to end with `.!?` (tail check), covered by GO-07 tests |
| Correlated-but-less-important words scored high | `oracle.py` score | Synonym-rich but content-dropping output passes 0.90 | §9.3 keyword check is the fallback and is ANDed (GO-10), asserted in runner tests |
| Duplicated filler list drifts | `oracle.py` | Oracle disagrees with normalizer | Regex built from `RuleBasedNormalizer.FILLERS` only (GO-08), tested against normalizer output |
| `encode` on empty strings | `oracle.py` cosine | Zero-norm vector → NaN cosine | Zero-vector guarded → `0.0`; empty output already FAILED before scoring (GO-09) |
| First CLI run downloads a model | network | Slow, may fail offline | Lazy load + propagate + exit 2 message; gates never touch the real model (mock mode) |
| Repeated model load per entry | `oracle.py` embedder | Slow real runs | Model cached on first `encode` inside `SemanticEmbedder` |
| Extra import breaks module import | `x9ai/oracle.py` | Gate/witness import fails in lean env | Import strictly inside `encode` (GO-03), asserted by test |

---

## Tech Decisions (only non-obvious ones)

| Decision | Choice | Rationale |
| -------- | ------ | --------- |
| Module layout | flat `x9ai/oracle.py` | Matches the flat-module precedent (`nlp-pipeline` rejected subpackages); one cohesive harness role |
| Similarity provider | `EmbeddingProvider` Protocol + `SemanticEmbedder` (lazy) + test `FakeEmbedder` | AD-011 pattern; deterministic gates, real model only in CLI runs |
| Cosine math | pure-Python over `list[float]` | sentence-transformers output converts to floats; no torch/numpy requirement in gates |
| Semantic threshold | module constant `SIMILARITY_THRESHOLD = 0.90` | §9.1 literal; inclusive `>=` |
| Filler list | import `RuleBasedNormalizer.FILLERS` | Single source of truth (spec assumption) |
| Model name default | `paraphrase-multilingual-MiniLM-L12-v2`, env override `ORACLE_EMBEDDING_MODEL` | §9.1 + user decision; PT-BR-capable multilingual model |
| Extra | `oracle = ["sentence-transformers>=2.2"]` | Keeps lean envs clean, mirrors `whisper` |
| CLI | `python -m x9ai.oracle run <dir>`; exits 0/1/2 | GO-15; subprocess-friendly for gates and UAT |

> **Project-level decisions:** none new beyond AD-009 already recorded (the `[oracle]`
> extra and embedding seam are feature-local).