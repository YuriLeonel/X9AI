"""Golden-transcript oracle harness (docs/spec.md §9).

Scores pipeline output against a golden corpus: semantic similarity (embedding-based,
≥0.90, §9.1), structural checks (§9.2), and keyword presence (§9.3). Consumed by the
CLI (`python -m x9ai.oracle run <dir>`) and by deterministic gates via injected fakes.
The embedding provider is lazy (AD-011 pattern): importing this module never requires
sentence-transformers; only an actual encode call does.
"""

import json
import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from x9ai.config import Settings
from x9ai.normalizer import RuleBasedNormalizer

SIMILARITY_THRESHOLD = 0.90

_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]")
_FILLERS_RE = re.compile(
    r"\b(?:%s)\b" % "|".join(re.escape(filler) for filler in RuleBasedNormalizer.FILLERS),
    re.IGNORECASE,
)
_ENDING_PUNCTUATION = (".", "!", "?")

ModelFactory = Callable[[Settings], object]


def _default_model_factory(settings: Settings) -> object:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model)


class EmbeddingProvider(Protocol):
    """Anything that maps a list of texts to a list of dense float vectors."""

    def encode(self, texts: list[str]) -> list[list[float]]: ...


class SemanticEmbedder:
    """Embeds texts via sentence-transformers, loading the model lazily on first call."""

    def __init__(
        self,
        settings: Settings | None = None,
        model_factory: ModelFactory | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self._model_factory = model_factory or _default_model_factory
        self._model: object | None = None

    def encode(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            self._model = self._model_factory(self.settings)
        raw = self._model.encode(texts)
        return [list(vector) for vector in raw]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two non-empty float vectors; zero-vector degenerates to 0.0."""
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (norm_a * norm_b)


@dataclass(frozen=True)
class StructuralOutcome:
    """Result of the §9.2 normalization-proof checks."""

    capital_start: bool
    ending_punctuation: bool
    no_fillers: bool

    @property
    def passed(self) -> bool:
        return self.capital_start and self.ending_punctuation and self.no_fillers


def structural_check(output: str) -> StructuralOutcome:
    """Verify every non-empty sentence starts capitalized, ends with punctuation, and
    contains no §9.2 filler (blacklist sourced from `RuleBasedNormalizer.FILLERS`)."""
    cleaned = output.strip()
    sentences = [sentence.strip() for sentence in _SENTENCE_RE.findall(cleaned)]
    capital_start = all(sentence and sentence[0].isupper() for sentence in sentences)
    ending_punctuation = cleaned.endswith(_ENDING_PUNCTUATION)
    no_fillers = _FILLERS_RE.search(cleaned) is None
    return StructuralOutcome(
        capital_start=capital_start,
        ending_punctuation=ending_punctuation,
        no_fillers=no_fillers,
    )


def keywords_present(keywords: Sequence[str], output: str) -> bool:
    """True when every declared keyword occurs in the output, case-insensitive substring
    matching (GO-10); an empty keyword list always passes (GO-11)."""
    lowered = output.lower()
    return all(keyword.lower() in lowered for keyword in keywords)


@dataclass(frozen=True)
class ScoreResult:
    """Conjunction of every §9 check for one pipeline output."""

    similarity: float
    semantic_passed: bool
    structural: StructuralOutcome
    keywords_passed: bool

    @property
    def passed(self) -> bool:
        return self.semantic_passed and self.structural.passed and self.keywords_passed


def score(
    golden: str,
    output: str,
    embedder: EmbeddingProvider,
    keywords: Sequence[str] = (),
) -> ScoreResult:
    """Score pipeline output against golden text: cosine similarity (≥0.90), structural
    checks, and declared-keyword presence."""
    golden_vec, output_vec = embedder.encode([golden, output])
    similarity = cosine(golden_vec, output_vec)
    return ScoreResult(
        similarity=similarity,
        semantic_passed=similarity >= SIMILARITY_THRESHOLD,
        structural=structural_check(output),
        keywords_passed=keywords_present(keywords, output),
    )


class CorpusError(Exception):
    """Raised when a corpus directory cannot be loaded or is malformed."""


@dataclass(frozen=True)
class Entry:
    """One golden-corpus test case."""

    id: str
    audio: Path
    golden: str
    language: str = "pt"
    keywords: tuple[str, ...] = ()


def load_corpus(corpus_dir: str | Path) -> list[Entry]:
    """Load `golden.json` from `corpus_dir` into a validated list of `Entry`; audio paths
    resolve relative to the corpus dir. Raises `CorpusError` on any manifest problem."""
    root = Path(corpus_dir)
    manifest = root / "golden.json"
    if not manifest.is_file():
        raise CorpusError(f"corpus manifest not found: {manifest}")
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CorpusError(f"invalid JSON in {manifest}: {exc}") from exc
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        raise CorpusError("golden.json must contain a non-empty 'entries' list")

    loaded: list[Entry] = []
    for raw in entries:
        if not isinstance(raw, dict):
            raise CorpusError(f"entry is not an object: {raw!r}")
        entry_id = raw.get("id")
        audio_rel = raw.get("audio")
        golden = raw.get("golden")
        if not isinstance(entry_id, str) or not entry_id.strip():
            raise CorpusError(f"entry missing non-empty 'id': {raw!r}")
        if not isinstance(audio_rel, str) or not audio_rel.strip():
            raise CorpusError(f"entry {entry_id} missing non-empty 'audio'")
        if not isinstance(golden, str) or not golden.strip():
            raise CorpusError(f"entry {entry_id} missing non-empty 'golden'")
        language = raw.get("language", "pt")
        if not isinstance(language, str) or not language.strip():
            raise CorpusError(f"entry {entry_id} has invalid 'language'")
        keywords_raw = raw.get("keywords", [])
        if not isinstance(keywords_raw, list) or not all(
            isinstance(keyword, str) for keyword in keywords_raw
        ):
            raise CorpusError(
                f"entry {entry_id} has invalid 'keywords' (expected a list of strings)"
            )
        loaded.append(
            Entry(
                id=entry_id,
                audio=(root / audio_rel).resolve(),
                golden=golden,
                language=language,
                keywords=tuple(keywords_raw),
            )
        )
    return loaded