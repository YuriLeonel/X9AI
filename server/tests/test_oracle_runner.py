"""Unit and integration tests for the oracle corpus loader, runner, and CLI (GO-09..16)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from x9ai.oracle import CorpusError, Entry, load_corpus, main, run_corpus


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


class _FakePipeline:
    def process(self, audio: bytes, language: str) -> str:
        if audio == b"boom":
            raise RuntimeError("transcriber exploded")
        if audio == b"blank":
            return "   "
        return "O aniversário foi ontem."


class _FakeEmbedder:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [self._vectors[text] for text in texts]


def _entry(
    tmp_path,
    entry_id: str,
    *,
    audio_bytes: bytes = b"\x00",
    golden: str = "O aniversário foi ontem.",
    keywords: tuple[str, ...] = (),
) -> Entry:
    audio = tmp_path / f"{entry_id}.wav"
    audio.write_bytes(audio_bytes)
    return Entry(id=entry_id, audio=audio, golden=golden, keywords=keywords)


def test_run_corpus_records_score_fields(tmp_path) -> None:
    entry = _entry(tmp_path, "a")
    embedder = _FakeEmbedder({"O aniversário foi ontem.": [1.0, 0.0]})
    report = run_corpus([entry], _FakePipeline(), embedder)
    assert len(report.outcomes) == 1
    outcome = report.outcomes[0]
    assert outcome.entry_id == "a"
    assert outcome.passed is True
    assert outcome.similarity == pytest.approx(1.0)
    assert outcome.structural is not None and outcome.structural.passed is True
    assert outcome.keywords_passed is True
    assert outcome.error is None


def test_run_corpus_empty_output_fails_before_scoring(tmp_path) -> None:
    entry = _entry(tmp_path, "a", audio_bytes=b"blank")
    report = run_corpus([entry], _FakePipeline(), _FakeEmbedder({}))
    outcome = report.outcomes[0]
    assert outcome.passed is False
    assert outcome.error == "empty output"
    assert outcome.similarity is None


def test_missing_audio_fails_entry_and_continues(tmp_path) -> None:
    missing = Entry(id="gone", audio=tmp_path / "nope.wav", golden="O é bom.")
    good = _entry(tmp_path, "ok")
    embedder = _FakeEmbedder({"O aniversário foi ontem.": [1.0, 0.0]})
    report = run_corpus([missing, good], _FakePipeline(), embedder)
    assert report.outcomes[0].passed is False
    assert "audio file not found" in (report.outcomes[0].error or "")
    assert report.outcomes[1].passed is True
    assert report.passed is False


def test_pipeline_exception_fails_entry_and_continues(tmp_path) -> None:
    boom = _entry(tmp_path, "boom", audio_bytes=b"boom")
    ok = _entry(tmp_path, "ok")
    embedder = _FakeEmbedder({"O aniversário foi ontem.": [1.0, 0.0]})
    report = run_corpus([boom, ok], _FakePipeline(), embedder)
    assert report.outcomes[0].passed is False
    assert "transcriber exploded" in (report.outcomes[0].error or "")
    assert report.outcomes[1].passed is True
    assert report.passed is False


def test_corpus_passes_only_when_every_entry_passes(tmp_path) -> None:
    embedder = _FakeEmbedder({"O aniversário foi ontem.": [1.0, 0.0]})
    bad = _entry(tmp_path, "bad", keywords=("praia",))
    ok = _entry(tmp_path, "ok")
    assert run_corpus([bad, ok], _FakePipeline(), embedder).passed is False
    assert run_corpus([ok], _FakePipeline(), embedder).passed is True


def test_keyword_failure_reflected_in_outcome(tmp_path) -> None:
    entry = _entry(tmp_path, "kw", keywords=("praia",))
    embedder = _FakeEmbedder({"O aniversário foi ontem.": [1.0, 0.0]})
    outcome = run_corpus([entry], _FakePipeline(), embedder).outcomes[0]
    assert outcome.similarity == pytest.approx(1.0)
    assert outcome.keywords_passed is False
    assert outcome.error is None
    assert outcome.passed is False


def test_run_is_deterministic_with_injected_fakes(tmp_path) -> None:
    entries = [_entry(tmp_path, "a"), _entry(tmp_path, "b", audio_bytes=b"boom")]
    embedder = _FakeEmbedder({"O aniversário foi ontem.": [1.0, 0.0]})
    first = run_corpus(entries, _FakePipeline(), embedder)
    second = run_corpus(entries, _FakePipeline(), embedder)
    assert first == second


def _corpus_dir(tmp_path, entry_ids) -> Path:
    for entry_id in entry_ids:
        (tmp_path / f"{entry_id}.wav").write_bytes(b"\x00")
    _write_manifest(
        tmp_path,
        [
            {"id": entry_id, "audio": f"{entry_id}.wav", "golden": "O aniversário foi ontem."}
            for entry_id in entry_ids
        ],
    )
    return tmp_path


def test_cli_exits_zero_on_passing_corpus(tmp_path, capsys) -> None:
    corpus = _corpus_dir(tmp_path, ["a", "b"])
    code = main(
        ["run", str(corpus)],
        pipeline=_FakePipeline(),
        embedder=_FakeEmbedder({"O aniversário foi ontem.": [1.0, 0.0]}),
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "[PASS] a" in captured.out
    assert "[PASS] b" in captured.out
    assert "similarity=1.000" in captured.out
    assert "structural=ok keywords=ok" in captured.out
    assert "CORPUS: PASS" in captured.out


def test_cli_exits_one_on_failing_entry(tmp_path, capsys) -> None:
    (tmp_path / "bad.wav").write_bytes(b"boom")
    _write_manifest(
        tmp_path, [{"id": "bad", "audio": "bad.wav", "golden": "O aniversário foi ontem."}]
    )
    code = main(
        ["run", str(tmp_path)],
        pipeline=_FakePipeline(),
        embedder=_FakeEmbedder({"O aniversário foi ontem.": [1.0, 0.0]}),
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "[FAIL] bad" in captured.out
    assert "CORPUS: FAIL" in captured.out


def test_cli_exits_two_on_missing_manifest(tmp_path, capsys) -> None:
    code = main(["run", str(tmp_path)])
    captured = capsys.readouterr()
    assert code == 2
    assert "golden.json" in captured.err


class _RaisingEmbedder:
    def encode(self, texts: list[str]) -> list[list[float]]:
        raise ImportError("No module named 'sentence_transformers'")


def test_cli_exits_two_when_embedding_extra_missing(tmp_path, capsys) -> None:
    corpus = _corpus_dir(tmp_path, ["a"])
    code = main(
        ["run", str(corpus)],
        pipeline=_FakePipeline(),
        embedder=_RaisingEmbedder(),
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "oracle" in captured.err


def test_cli_module_invokable_and_verdict_bound_offline(tmp_path) -> None:
    corpus = _corpus_dir(tmp_path, ["a"])
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    proc = subprocess.run(
        [sys.executable, "-m", "x9ai.oracle", "run", str(corpus)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 1
    assert "CORPUS: FAIL" in proc.stdout