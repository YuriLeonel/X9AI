"""Unit tests for the rule-based PT-BR normalizer (NLP-10..14)."""

import pytest

from x9ai.normalizer import Normalizer, RuleBasedNormalizer


def test_normalizer_is_abstract() -> None:
    with pytest.raises(TypeError):
        Normalizer()  # type: ignore[abstract]


def test_removes_each_filler_whole_word() -> None:
    normalizer = RuleBasedNormalizer()
    assert normalizer.normalize("o tipo é bom") == "O é bom."
    assert normalizer.normalize("vamos né") == "Vamos."
    assert normalizer.normalize("então vamos") == "Vamos."
    assert normalizer.normalize("ééé legal") == "Legal."
    assert normalizer.normalize("um carro") == "Carro."
    assert normalizer.normalize("uh ok") == "Ok."


def test_removes_fillers_case_insensitively() -> None:
    assert RuleBasedNormalizer().normalize("TIPO oi ENTÃO bom") == "Oi bom."


def test_filler_substring_not_removed() -> None:
    assert RuleBasedNormalizer().normalize("mundo é bom") == "Mundo é bom."


def test_capitalizes_first_character() -> None:
    assert RuleBasedNormalizer().normalize("o é bom") == "O é bom."


def test_appends_period_when_missing() -> None:
    assert RuleBasedNormalizer().normalize("ola mundo") == "Ola mundo."


def test_preserves_existing_ending_punctuation() -> None:
    normalizer = RuleBasedNormalizer()
    assert normalizer.normalize("Olá.") == "Olá."
    assert normalizer.normalize("Olá!") == "Olá!"
    assert normalizer.normalize("Olá?") == "Olá?"


def test_is_deterministic() -> None:
    normalizer = RuleBasedNormalizer()
    text = "o tipo então é bom"
    assert normalizer.normalize(text) == normalizer.normalize(text)


def test_fillers_only_returns_empty_and_collapses_whitespace() -> None:
    normalizer = RuleBasedNormalizer()
    assert normalizer.normalize("tipo") == ""
    assert normalizer.normalize("ééé uh") == ""
    assert normalizer.normalize("o   tipo   é") == "O é."


def test_english_fillers_use_same_rules() -> None:
    assert RuleBasedNormalizer().normalize("um uh oi") == "Oi."
