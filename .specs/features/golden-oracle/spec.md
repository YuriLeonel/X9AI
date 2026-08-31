# golden-oracle Specification

## Problem Statement

AI output is non-deterministic, so `docs/spec.md` §9 mandates a golden-transcript
oracle: a small set of PT-BR clips with known golden text, scored for semantic similarity
(≥90%), structural normality (capitalized/punctuated sentences, no §9.2 fillers), and
keyword presence. No harness exists yet — `nlp-pipeline` shipped the pipeline (AD-008,
AD-011) but nothing gates the corpus. This feature builds the oracle harness: a scoring
library, a corpus runner with mock mode (AD-009), and a CLI that drives `RealPipeline`
over recorded clips before final UAT.

## Goals

- [ ] Oracle scores pipeline output per corpus entry: cosine similarity ≥ 0.90 (§9.1), structural checks (§9.2), keyword presence (§9.3)
- [ ] Similarity uses a standard local embedding model (sentence-transformers), isolated behind an optional `[oracle]` extra with a lazy import and an injectable fake for deterministic gates (whisper AD-011 pattern)
- [ ] Corpus is a pluggable directory (manifest + audio); mock mode runs the full flow offline with an injected pipeline/fake embedder (AD-009)
- [ ] `python -m x9ai.oracle run <corpus-dir>` emits a per-entry PASS/FAIL report and exits non-zero when the corpus does not pass (§9 "a v1 PASS requires the entire corpus")

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Recording real PT-BR clips / UAT audio | Manual pre-UAT step (§9); the harness is the tool, not the recording |
| Auto-extraction of keywords (§9.3) | Decision: manual keyword lists per entry — deterministic, no NLP-extra dependency |
| English normalization rules | §2 fixes PT-BR primary; EN entries reuse the same fills/structural rules |
| Cloud embedding APIs | §5/AD-004 local-first; embedding model is local | 
| Persisted / HTML reports | CLI prints to stdout only in v1 |
| Model download automation | Lazy load only; operator installs the `[oracle]` extra |
| Per-corpus thresholds override | §9 fixes ≥ 90% globally |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Embedding engine | `sentence-transformers` via new `[oracle]` extra; model `paraphrase-multilingual-MiniLM-L12-v2`, env `ORACLE_EMBEDDING_MODEL` override | §9.1 "standard embedding model"; MiniLM multilingual is PT-BR capable; matches AD-011 extra pattern | y |
| Embedding absence in gates | Injected fake embedder; real `sentence-transformers` never touched offline | Deterministic gates (AD-009 mock mode); mirrors `model_factory` | y |
| Laziness of embedding import | Import inside the encode call only; module import + CLI help work without `[oracle]` | Same contract as NLP-07 | y |
| Similarity threshold semantics | `similarity >= 0.90` passes; both texts encoded, cosine of their vectors | §9.1; inclusive threshold | y |
| Keyword matching | Case-insensitive substring search on the output | §9.3 fallback check; tolerates PT-BR inflection ("parque" ∈ "parques") | y |
| Filler blacklist source | Reused from `RuleBasedNormalizer.FILLERS` (`"tipo","né","então","ééé","um","uh"`), never duplicated | Single source of truth with NL-11 pipeline | y |
| Structural sentence split | Split on `.`, `!`, `?`; a non-empty sentence must start uppercase AND end with one of `.`, `!`, `?` | §9.2 normalization proof | y |
| Empty/whitespace output | Entry scored FAILED by the runner before semantic scoring | Silence ≈ no text; §9 PASS needs meaningful output | y |
| Missing audio file | Entry FAILED with recorded error; runner continues to next entry | One bad clip must not mask the rest of the corpus | y |
| Invalid manifest | Corpus load aborts with a clear error (no silent partial run) | Config drift visible, not hidden | y |
| Pipeline failure per entry | Caught and recorded as entry FAILED; runner continues | Same rationale as missing audio | y |
| Corpus run ordering | Sequential, manifest order (deterministic) | No concurrency value in a handful of clips | y |
| Manifest format | `golden.json`: `{"entries": [{"id", "audio", "language", "golden", "keywords": []}]}`; `keywords` optional, `language` defaults `"pt"` | Explicit fixture contract for tests and real corpus | y |
| CLI needs | Requires `[whisper]` + `[oracle]` extras; missing extras surface as a clear CLI error | CLI is the real-clip runner; gates use injected fakes | n |
| English (`en`) entries | Same blacklist (already includes "um"/"uh") and structural rules apply | §9.2 exact list; NL-13 precedent | n |

**Open questions:** none - all resolved or logged above.

**Implicit-requirement dimensions sweep:** auth/rate limits N/A (local dev tool, single
user, §2); idempotency/retry N/A (stateless scoring; each run re-reads the corpus);
concurrency/ordering — sequential manifest order; data lifecycle N/A (reads-only, no
persistence); state-transition integrity N/A; input validation — manifest schema +
missing-audio handled (above); failure/partial-failure — per-entry errors captured, load
errors abort; external-dependency failure — `[oracle]`/`[whisper]` missing and embedder
encode raise are surfaced per-entry (runner) or as a CLI abort (load); observability —
per-entry report + exit code.

---

## User Stories

### P1: Semantic similarity scoring — "Prove the meaning survives" ⭐ MVP

**User Story**: As a developer, I want the oracle to score pipeline output against golden
text with an embedding-based cosine similarity, so that synonyms don't fail the corpus
(§9.1).

**Why P1**: The primary acceptance check in §9.

**Acceptance Criteria**:

1. GO-01 The oracle SHALL provide a semantic scorer that encodes two texts with the configured embedding provider and returns their cosine similarity as a float in `[0,1]`.
2. GO-02 WHERE the `[oracle]` extra is installed THEN the oracle SHALL encode texts using sentence-transformers with the `ORACLE_EMBEDDING_MODEL` model (default `paraphrase-multilingual-MiniLM-L12-v2`).
3. GO-03 WHERE the `[oracle]` extra is absent THEN importing the semantic scoring module SHALL NOT fail, and only an actual encode call SHALL raise.
4. GO-04 WHEN an embedding provider is injected THEN the oracle SHALL use it instead of sentence-transformers, keeping scores deterministic for gates.
5. GO-05 WHEN an entry's similarity is greater than or equal to `0.90` THEN the oracle SHALL mark the entry's semantic check PASSED, otherwise FAILED.

**Independent Test**: With a fake embedder returning known vectors (identical texts → 1.0,
orthogonal → 0.0), assert GO-01/GO-04/GO-05; import the module without `[oracle]` (no fail,
GO-03); the lazy import path is exercised only under the extra (guarded).

---

### P1: Structural checks — "Normalization proof" ⭐ MVP

**User Story**: As a developer, I want the oracle to verify every output sentence starts
capitalized and ends with punctuation and that no §9.2 filler remains, so that the §9.2
normalization proof is code (AD-008).

**Why P1**: The §9.2 acceptance check, straight against `RuleBasedNormalizer` output.

**Acceptance Criteria**:

1. GO-06 The oracle SHALL mark the structural check FAILED when any non-empty sentence in the output does not start with an uppercase letter.
2. GO-07 The oracle SHALL mark the structural check FAILED when any non-empty sentence in the output does not end with `.`, `!`, or `?`.
3. GO-08 The oracle SHALL mark the structural check FAILED when the output contains any filler from the `RuleBasedNormalizer.FILLERS` blacklist as a case-insensitive whole word.
4. GO-09 WHEN the output is empty or whitespace-only THEN the oracle SHALL mark the entry FAILED.

**Independent Test**: Feed outputs missing capitalization, missing punctuation, containing
`"tipo"`/`"ééé"`, and blank; assert each tripped check; assert a clean normalized sentence
passes all four.

---

### P1: Keyword presence — "Crucial tokens survive" ⭐ MVP

**User Story**: As a developer, I want the oracle to require the manifest-declared keywords
of the golden text to appear in the output, so that critical meaning survives even if
similarity stays high (§9.3).

**Why P1**: The §9.3 fallback; guards against semantically similar but content-dropping output.

**Acceptance Criteria**:

1. GO-10 The oracle SHALL mark the keyword check PASSED when every manifest-declared keyword of an entry appears in the entry's output, matching case-insensitively as a substring.
2. GO-11 WHEN an entry declares no keywords THEN the oracle SHALL mark the keyword check passed with no keyword assertions.

**Independent Test**: Golden `"O aniversário foi ontem no parque."` with
`keywords: ["aniversário", "parque"]` — output keeping both passes, dropping `parque`
fails; an entry with empty `keywords` always passes GO-11.

---

### P1: Corpus runner with report — "One command, whole-corpus verdict" ⭐ MVP

**User Story**: As a developer, I want to point the runner at a corpus directory and get a
per-entry PASS/FAIL report plus a corpus-wide verdict, so that a v1 PASS is one command and
one exit code (§9).

**Why P1**: The harness's core loop; the CLI is the pre-UAT gate for real clips (AD-009).

**Acceptance Criteria**:

1. GO-12 The oracle SHALL load a corpus directory whose `golden.json` manifest declares entries each with `id`, `audio`, `golden`, optional `keywords`, and `language` defaulting to `pt`.
2. GO-13 WHEN the runner processes an entry THEN it SHALL feed the entry's audio bytes and language to the configured pipeline, run all applicable checks, and record a per-entry report including similarity score and per-check results.
3. GO-14 The oracle SHALL report the corpus as PASSED only when every entry passes every applicable check, and FAILED otherwise.
4. GO-15 WHEN run as `python -m x9ai.oracle run <corpus-dir>` THEN the CLI SHALL run the corpus through the real default pipeline and the real embedding model, print the per-entry report, and exit zero if the corpus passes and non-zero otherwise.

**Independent Test**: Build a corpus dir with a fake transcriber pipeline and fake
embedder; assert GO-12 loads it, GO-13 records scores/results, GO-14 flips on a failing
entry, and GO-15 the CLI subprocess mirrors the verdict with exit codes.

---

### P1: Mock mode — "Offline deterministic gates" ⭐ MVP

**User Story**: As a developer, I want to run the full oracle flow with an injected fake
pipeline and fake embedder, so that harness tests and post-merge checks run offline with
zero model downloads (AD-009).

**Why P1**: Keeps gates deterministic without `[whisper]`/`[oracle]` extras or audio.

**Acceptance Criteria**:

1. GO-16 WHEN a mock pipeline and a mock embedding provider are injected THEN the oracle SHALL run a full corpus through load → transcribe → score → report deterministically, without audio decoding, model download, or network access.

**Independent Test**: The corpus-runner tests all use injected fakes (GO-16); the same
scoring functions produce byte-identical reports across two runs.

---

## Edge Cases

- IF the manifest references a missing audio file THEN the runner SHALL mark that entry FAILED with the captured error and continue.
- IF the manifest is malformed or a required entry field is missing THEN the runner SHALL abort the run with a clear error.
- IF the pipeline raises for an entry THEN the runner SHALL record that entry as FAILED and continue to the next.
- IF an entry-level failure occurs THEN the runner SHALL print the entry's error alongside its report line.
- IF similarity equals exactly `0.90` THEN the semantic check SHALL be PASSED (inclusive).
- IF an entry has `language` `en` THEN the same blacklist and structural rules SHALL apply (§9.2; NL-13 precedent).

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| GO-01 | P1: Semantic similarity | In Tasks | In Tasks |
| GO-02 | P1: Semantic similarity | In Tasks | In Tasks |
| GO-03 | P1: Semantic similarity | In Tasks | In Tasks |
| GO-04 | P1: Semantic similarity | In Tasks | In Tasks |
| GO-05 | P1: Semantic similarity | In Tasks | In Tasks |
| GO-06 | P1: Structural checks | In Tasks | In Tasks |
| GO-07 | P1: Structural checks | In Tasks | In Tasks |
| GO-08 | P1: Structural checks | In Tasks | In Tasks |
| GO-09 | P1: Structural checks | Design | Pending |
| GO-10 | P1: Keyword presence | In Tasks | In Tasks |
| GO-11 | P1: Keyword presence | In Tasks | In Tasks |
| GO-12 | P1: Corpus runner | In Tasks | In Tasks |
| GO-13 | P1: Corpus runner | Design | Pending |
| GO-14 | P1: Corpus runner | In Tasks | In Tasks |
| GO-15 | P1: Corpus runner | Design | Pending |
| GO-16 | P1: Mock mode | Design | Pending |

**Coverage:** 16 total, 0 mapped to tasks, 16 unmapped ⚠️

---

## Success Criteria

- [ ] Corpus runner, invoked with injected mocks, produces a per-entry report and a byte-identical re-run (deterministic, offline — mock mode)
- [ ] A corpus whose entries all meet ≥ 0.90 similarity + structural + keyword checks reports PASSED and exits zero; introducing one failing entry flips both
- [ ] Semantic scoring module imports without `[oracle]`; only encode calls raise (lazy import)
- [ ] Filler blacklist is sourced from `RuleBasedNormalizer.FILLERS`, not duplicated