"""Unit tests for the oracle semantic scoring core (GO-01..04)."""

import math

import pytest

from x9ai.config import Settings
from x9ai.oracle import SemanticEmbedder, cosine, keywords_present, score, structural_check


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


def test_structural_missing_sentence_capital_fails() -> None:
    outcome = structural_check("ola mundo.")
    assert outcome.capital_start is False
    assert outcome.passed is False


def test_structural_unterminated_sentence_fails() -> None:
    outcome = structural_check("Ola mundo")
    assert outcome.ending_punctuation is False


def test_structural_multi_sentence_mixed_casing_fails() -> None:
    outcome = structural_check("Ola. mundo bom.")
    assert outcome.capital_start is False
    assert outcome.passed is False


def test_structural_clean_sentence_passes_all() -> None:
    outcome = structural_check("O aniversário foi ontem no parque!")
    assert outcome.capital_start is True
    assert outcome.ending_punctuation is True
    assert outcome.no_fillers is True
    assert outcome.passed is True


def test_structural_filler_present_fails_from_shared_blacklist() -> None:
    assert structural_check("O tipo é bom.").no_fillers is False
    assert structural_check("O ééé é bom.").no_fillers is False


def test_structural_filler_matches_case_insensitive_whole_word() -> None:
    assert structural_check("O TIPO é bom.").no_fillers is False
    assert structural_check("O tipografia é boa.").no_fillers is True


def test_keywords_requires_each_declared_keyword() -> None:
    output = "O aniversário foi ontem no parque."
    assert keywords_present(["aniversário", "parque"], output) is True
    assert keywords_present(["aniversário", "parque", "praia"], output) is False


def test_keywords_match_case_insensitive_substring_and_empty_passes() -> None:
    assert keywords_present(["PARQUE"], "O aniversário foi no parque.") is True
    assert keywords_present(["aniversário"], "Os aniversários foram ontem.") is True
    assert keywords_present([], "Qualquer texto.") is True


class _FakeEmbedder:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [self._vectors[text] for text in texts]


def test_score_passes_at_threshold_boundary_and_fails_below() -> None:
    embedder = _FakeEmbedder(
        {
            "golden": [1.0, 0.0, 0.0],
            "at": [0.9, math.sqrt(0.19), 0.0],
            "below": [0.8, 0.6, 0.0],
        }
    )
    at = score("golden", "at", embedder)
    below = score("golden", "below", embedder)
    assert at.similarity == pytest.approx(0.90)
    assert at.semantic_passed is True
    assert below.similarity == pytest.approx(0.80)
    assert below.semantic_passed is False


def test_score_similarity_is_one_for_identical_texts() -> None:
    embedder = _FakeEmbedder({"golden": [1.0, 2.0]})
    result = score("golden", "golden", embedder)
    assert result.similarity == pytest.approx(1.0)
    assert result.semantic_passed is True


def test_score_result_passed_requires_all_checks() -> None:
    embedder = _FakeEmbedder(
        {
            "golden": [1.0, 0.0],
            "O aniversário foi ontem.": [1.0, 0.0],
            "O tipo é bom.": [1.0, 0.0],
        }
    )
    clean = score("golden", "O aniversário foi ontem.", embedder)
    assert clean.semantic_passed is True
    assert clean.passed is True
    filler = score("golden", "O tipo é bom.", embedder)
    assert filler.semantic_passed is True
    assert filler.passed is False
    missing = score("golden", "O aniversário foi ontem.", embedder, keywords=["praia"])
    assert missing.keywords_passed is False
    assert missing.passed is False