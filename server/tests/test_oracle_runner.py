"""Unit tests for the oracle corpus loader (GO-12)."""

import json

import pytest

from x9ai.oracle import CorpusError, load_corpus


def _write_manifest(corpus_dir, entries) -> None:
    (corpus_dir / "golden.json").write_text(
        json.dumps({"entries": entries}), encoding="utf-8"
    )


def test_load_corpus_reads_valid_manifest_with_defaults(tmp_path) -> None:
    _write_manifest(
        tmp_path,
        [{"id": "a", "audio": "clips/a.wav", "golden": "O aniversário foi ontem."}],
    )
    entries = load_corpus(tmp_path)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.id == "a"
    assert entry.language == "pt"
    assert entry.golden == "O aniversário foi ontem."
    assert entry.keywords == ()
    assert entry.audio == (tmp_path / "clips" / "a.wav").resolve()


def test_load_corpus_reads_language_and_keywords(tmp_path) -> None:
    _write_manifest(
        tmp_path,
        [
            {
                "id": "b",
                "audio": "b.wav",
                "golden": "Hello there.",
                "language": "en",
                "keywords": ["hello", "there"],
            }
        ],
    )
    entry = load_corpus(tmp_path)[0]
    assert entry.language == "en"
    assert entry.keywords == ("hello", "there")


def test_missing_manifest_raises_corpus_error(tmp_path) -> None:
    with pytest.raises(CorpusError, match="golden.json"):
        load_corpus(tmp_path)


def test_malformed_json_raises_corpus_error(tmp_path) -> None:
    (tmp_path / "golden.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(CorpusError, match="invalid JSON"):
        load_corpus(tmp_path)


def test_missing_required_field_and_empty_entries_raise(tmp_path) -> None:
    _write_manifest(tmp_path, [{"id": "c", "audio": "c.wav"}])
    with pytest.raises(CorpusError, match="c .*golden"):
        load_corpus(tmp_path)
    _write_manifest(tmp_path, [])
    with pytest.raises(CorpusError, match="non-empty"):
        load_corpus(tmp_path)