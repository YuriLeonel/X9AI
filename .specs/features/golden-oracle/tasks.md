# golden-oracle Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/golden-oracle/design.md`
**Status**: Draft

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: `AGENTS.md` (golden-corpus oracle is the test harness: ≥90% semantic similarity, structural checks, keyword presence — never weaken/delete these), `docs/spec.md` §9, `server/pyproject.toml` (`testpaths = ["tests"]`, ruff line-length 100). No pytest coverage thresholds or CI gate config in repo.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Oracle domain scoring (cosine, embedder protocol, structural, keyword, score) | unit | All branches; 1:1 to GO-01..11; edge cases: zero-vector cosine, §9.2 blacklist from `FILLERS`, empty-keywords, 0.90 boundary | `server/tests/test_oracle_scoring.py` | `pytest tests/test_oracle_scoring.py tests/test_oracle_runner.py` |
| Corpus loader (manifest schema + validation) | unit | GO-12 + every listed manifest edge (missing file, bad JSON, missing fields, audio resolution) | `server/tests/test_oracle_runner.py` | `pytest tests/test_oracle_runner.py` |
| Runner + report orchestration | unit | GO-09/13/14/16 + all listed edge cases (missing audio, pipeline raise, empty output, determinism) | `server/tests/test_oracle_runner.py` | `pytest tests/test_oracle_runner.py` |
| CLI (`main` + `python -m x9ai.oracle`) | integration | GO-15 happy + edge + error exit paths (0/1/2), one subprocess run | `server/tests/test_oracle_runner.py` | `pytest tests/test_oracle_runner.py` |
| Config (`Settings.embedding_model`) | unit | Existing `test_config.py` floor: default + env override + unset fallback | `server/tests/test_config.py` | `pytest tests/test_config.py` |
| Entity / pyproject extra | none | - (build gate only) | - | - |

## Gate Check Commands

> Generated from codebase - confirm before Execute.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After tasks with unit tests only | `server/.venv/bin/python -m pytest <affected test files> -q` |
| Full | After tasks with integration tests (CLI) and phase completion | `server/.venv/bin/python -m pytest -q` |
| Build | After config/entity-only tasks and final phase | `server/.venv/bin/ruff check x9ai tests && server/.venv/bin/python -m pytest -q` |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Oracle harness (single tight dependency chain)

```
T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8
```

8 tasks = one batch (≤ ~8) → inline execution, no sub-agents.

---

## Task Breakdown

### T1: Add oracle embedding model setting

**What**: Extend `Settings` with `embedding_model` and read it from `ORACLE_EMBEDDING_MODEL`.
**Where**: `server/x9ai/config.py` (modify)
**Depends on**: None
**Reuses**: frozen `Settings` + `_env_str` pattern
**Requirement**: GO-02

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `Settings().embedding_model == "paraphrase-multilingual-MiniLM-L12-v2"`
- [ ] `Settings.from_env()` honours `ORACLE_EMBEDDING_MODEL` and falls back when unset/blank
- [ ] Gate check passes: `server/.venv/bin/python -m pytest tests/test_config.py -q`
- [ ] Test count: 3 tests in `test_config.py` pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(server): add oracle embedding model setting`

**Status**: ✅ Done

---

### T2: Add `[oracle]` extra

**What**: Register the `oracle` optional dependency in project metadata.
**Where**: `server/pyproject.toml` (modify)
**Depends on**: T1
**Reuses**: existing `[project.optional-dependencies]` block
**Requirement**: GO-02, GO-03

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `oracle = ["sentence-transformers>=2.2"]` present under `[project.optional-dependencies]`
- [ ] Build gate passes: `server/.venv/bin/ruff check x9ai tests && server/.venv/bin/python -m pytest -q`

**Tests**: none
**Gate**: build

**Commit**: `build(server): add oracle extra for sentence-transformers`

**Status**: ✅ Done

---

### T3: Add semantic scoring core

**What**: Create `x9ai/oracle.py` with `SIMILARITY_THRESHOLD`, `EmbeddingProvider` protocol, pure-Python `cosine`, and lazy `SemanticEmbedder`.
**Where**: `server/x9ai/oracle.py` (new)
**Depends on**: T2
**Reuses**: lazy-extra pattern from `transcriber.py:18-25`; `Settings.embedding_model`
**Requirement**: GO-01, GO-03, GO-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `cosine` returns 1.0 for identical vectors, 0.0 for orthogonal, 0.0 on zero-vector input
- [ ] `SemanticEmbedder` imports `SentenceTransformer` only inside `encode`; constructing it imports `x9ai.oracle` without the extra without failing, and `encode` raises `ImportError` when the extra is absent
- [ ] An injected `EmbeddingProvider` is used instead of sentence-transformers (GO-04)
- [ ] Gate check passes: `server/.venv/bin/python -m pytest tests/test_oracle_scoring.py -q`
- [ ] Test count: 6 tests in `test_oracle_scoring.py` pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(server): add oracle semantic scoring core`

**Status**: ✅ Done

---

### T4: Add structural and keyword checks

**What**: Extend `x9ai/oracle.py` with `StructuralOutcome`, `structural_check`, and `keywords_present` (reusing `RuleBasedNormalizer.FILLERS`).
**Where**: `server/x9ai/oracle.py` (modify)
**Depends on**: T3
**Reuses**: `RuleBasedNormalizer.FILLERS` (single source of truth)
**Requirement**: GO-06, GO-07, GO-08, GO-10, GO-11

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `structural_check` marks `capital_start` false when a non-empty sentence starts lowercase (GO-06), `ending_punctuation` false when the tail does not end in `.`/`!`/`?` (GO-07), `no_fillers` false when a `FILLERS` word appears as case-insensitive whole word (GO-08)
- [ ] `keywords_present` requires every keyword (case-insensitive substring) and returns True for an empty keyword list (GO-10, GO-11)
- [ ] Filler regex is built from `RuleBasedNormalizer.FILLERS`, not a copied list
- [ ] Gate check passes: `server/.venv/bin/python -m pytest tests/test_oracle_scoring.py -q`
- [ ] Test count: 8 tests pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(server): add oracle structural and keyword checks`

**Status**: ✅ Done

---

### T5: Add semantic score composition

**What**: Extend `x9ai/oracle.py` with `ScoreResult` and `score()` combining cosine threshold + structural + keyword into one verdict.
**Where**: `server/x9ai/oracle.py` (modify)
**Depends on**: T4
**Reuses**: functions from T3/T4
**Requirement**: GO-05, GO-14

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `score()` returns `semantic_passed` True for similarity exactly `0.90` and False below (inclusive threshold, GO-05)
- [ ] `ScoreResult.passed` is the conjunction of semantic, structural, and keyword results (GO-14)
- [ ] Gate check passes: `server/.venv/bin/python -m pytest tests/test_oracle_scoring.py -q`
- [ ] Test count: 3 tests pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(server): add oracle semantic score composition`

**Status**: ✅ Done

---

### T6: Add corpus loader

**What**: Extend `x9ai/oracle.py` with `Entry`, `CorpusError`, and `load_corpus` reading `golden.json` with validation and audio-path resolution.
**Where**: `server/x9ai/oracle.py` (modify)
**Depends on**: T5
**Reuses**: `json`, `os`, `dataclasses` from stdlib
**Requirement**: GO-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `load_corpus` parses entries with `language` defaulting to `"pt"` and `keywords` defaulting to empty (GO-12)
- [ ] Audio paths resolve relative to the corpus dir to absolute paths
- [ ] Missing `golden.json`, invalid JSON, empty entries list, and missing required fields raise `CorpusError` with a message naming the offending state
- [ ] Gate check passes: `server/.venv/bin/python -m pytest tests/test_oracle_runner.py -q`
- [ ] Test count: 5 tests in `test_oracle_runner.py` pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(server): add oracle corpus loader`

---

### T7: Add corpus runner

**What**: Extend `x9ai/oracle.py` with `EntryOutcome`, `CorpusReport`, and `run_corpus` (per-entry error capture + score, corpus verdict).
**Where**: `server/x9ai/oracle.py` (modify)
**Depends on**: T6
**Reuses**: `score`, `Entry`, `Pipeline` seam
**Requirement**: GO-09, GO-13, GO-14, GO-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Missing audio file → entry FAILED with `"audio file not found: <path>"`, run continues
- [ ] Pipeline exception → entry FAILED with the error, run continues
- [ ] Empty/whitespace output → entry FAILED `"empty output"` before scoring (GO-09)
- [ ] Healthy entry → report carries `similarity`, structural, and keyword results (GO-13); corpus `passed` only when all entries pass (GO-14)
- [ ] Two runs with injected fakes over the same corpus produce identical reports (GO-16 determinism)
- [ ] Gate check passes: `server/.venv/bin/python -m pytest tests/test_oracle_runner.py -q`
- [ ] Test count: 7 tests pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(server): add oracle corpus runner`

---

### T8: Add oracle CLI

**What**: Extend `x9ai/oracle.py` with argparse `main(argv)` (`run <corpus-dir>`) and the `__main__` guard; print per-entry report + corpus verdict.
**Where**: `server/x9ai/oracle.py` (modify)
**Depends on**: T7
**Reuses**: `RealPipeline`, `WhisperTranscriber`, `RuleBasedNormalizer`, `Settings.from_env`
**Requirement**: GO-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `main(["run", dir])` returns 0 on corpus PASS, 1 on corpus FAIL, 2 on `CorpusError` / missing extra, with an informative report on stdout
- [ ] `python -m x9ai.oracle run <dir>` subprocess exit codes mirror `main()` (one integration check)
- [ ] Full gate passes: `server/.venv/bin/python -m pytest -q`
- [ ] Test count: 4 tests pass (no silent deletions); full suite stays green

**Tests**: integration
**Gate**: full

**Commit**: `feat(server): add oracle CLI runner`

---

## Phase Execution Map

Visual representation of task ordering. Phases run in sequence, and tasks within a phase run in order:

```
Phase 1:  T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8
```

Execution is strictly sequential - no intra-phase parallelism. 8 tasks = one batch (≤ ~8) → execute inline in the main window.

---

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: Settings.embedding_model | 1 file config change | ✅ Granular |
| T2: oracle extra | 1 file metadata change | ✅ Granular |
| T3: scoring core (protocol + cosine + embedder) | 1 file, 1 cohesive concern | ✅ Granular |
| T4: structural + keyword checks | 1 file, 2 cohesive checks (related) | ✅ Granular |
| T5: score composition | 1 file, 1 function set | ✅ Granular |
| T6: corpus loader | 1 file, 1 concern | ✅ Granular |
| T7: corpus runner | 1 file, 1 concern | ✅ Granular |
| T8: CLI | 1 file, 1 concern | ✅ Granular |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | T1 (start) | ✅ Match |
| T2 | T1 | T1→T2 | ✅ Match |
| T3 | T2 | T2→T3 | ✅ Match |
| T4 | T3 | T3→T4 | ✅ Match |
| T5 | T4 | T4→T5 | ✅ Match |
| T6 | T5 | T5→T6 | ✅ Match |
| T7 | T6 | T6→T7 | ✅ Match |
| T8 | T7 | T7→T8 | ✅ Match |

All `Depends on` entries have a diagram arrow; every arrow has a matching `Depends on`; no forward-phase dependencies (single phase).

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1 | Config layer | unit (existing floor) | unit | ✅ OK |
| T2 | Entity/pyproject extra | none (build gate) | none | ✅ OK |
| T3 | Oracle domain (scoring core) | unit | unit | ✅ OK |
| T4 | Oracle domain (checks) | unit | unit | ✅ OK |
| T5 | Oracle domain (score) | unit | unit | ✅ OK |
| T6 | Corpus loader | unit | unit | ✅ OK |
| T7 | Runner + report | unit | unit | ✅ OK |
| T8 | CLI | integration | integration | ✅ OK |

No deferred tests; every code layer with a required test type carries its tests in-task.