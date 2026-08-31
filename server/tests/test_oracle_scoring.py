"""Unit tests for the oracle semantic scoring core (GO-01..04)."""

import pytest

from x9ai.config import Settings
from x9ai.oracle import SemanticEmbedder, cosine


class _FakeModel:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [self._vectors[text] for text in texts]


def test_cosine_identical_vectors_is_one() -> None:
    assert cosine([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]) == pytest.approx(1.0)


def test_cosine_orthogonal_vectors_is_zero() -> None:
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_zero_vector_returns_zero() -> None:
    assert cosine([0.0, 0.0], [1.0, 0.0]) == pytest.approx(0.0)


def test_semantic_embedder_uses_injected_model_factory() -> None:
    calls: list[Settings] = []

    def factory(settings: Settings) -> object:
        calls.append(settings)
        return _FakeModel({"a": [1.0, 0.0], "b": [0.0, 1.0]})

    embedder = SemanticEmbedder(Settings(), factory)
    assert embedder.encode(["a", "b"]) == [[1.0, 0.0], [0.0, 1.0]]
    assert len(calls) == 1
    assert calls[0].embedding_model == "paraphrase-multilingual-MiniLM-L12-v2"


def test_oracle_module_imports_without_oracle_extra() -> None:
    import x9ai.oracle  # noqa: F401  # must not require sentence-transformers


def test_semantic_embedder_encode_raises_when_extra_missing() -> None:
    def no_import_factory(settings: Settings) -> object:
        raise ImportError("No module named 'sentence_transformers'")

    embedder = SemanticEmbedder(Settings(), no_import_factory)
    with pytest.raises(ImportError):
        embedder.encode(["o texto é bom"])