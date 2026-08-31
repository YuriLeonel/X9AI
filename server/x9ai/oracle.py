"""Golden-transcript oracle harness (docs/spec.md §9).

Scores pipeline output against a golden corpus: semantic similarity (embedding-based,
≥0.90, §9.1), structural checks (§9.2), and keyword presence (§9.3). Consumed by the
CLI (`python -m x9ai.oracle run <dir>`) and by deterministic gates via injected fakes.
The embedding provider is lazy (AD-011 pattern): importing this module never requires
sentence-transformers; only an actual encode call does.
"""

import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
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