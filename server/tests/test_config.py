"""Unit tests for settings (SRV-07 audio-size bound)."""

from dataclasses import FrozenInstanceError

import pytest

from x9ai.config import Settings


def test_default_max_audio_bytes_is_50_mib() -> None:
    assert Settings().max_audio_bytes == 50 * 1024 * 1024


def test_from_env_reads_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_AUDIO_BYTES", "1024")
    assert Settings.from_env().max_audio_bytes == 1024


def test_from_env_falls_back_on_malformed_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_AUDIO_BYTES", "not-a-number")
    assert Settings.from_env().max_audio_bytes == 50 * 1024 * 1024


def test_from_env_falls_back_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MAX_AUDIO_BYTES", raising=False)
    assert Settings.from_env().max_audio_bytes == 50 * 1024 * 1024


def test_settings_are_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        Settings().max_audio_bytes = 1  # type: ignore[misc]


def test_default_whisper_model_is_medium() -> None:
    settings = Settings()
    assert settings.whisper_model == "medium"
    assert settings.whisper_device == "auto"
    assert settings.whisper_compute_type == "default"


def test_from_env_reads_whisper_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHISPER_MODEL", "small")
    monkeypatch.setenv("WHISPER_DEVICE", "cpu")
    monkeypatch.setenv("WHISPER_COMPUTE_TYPE", "int8")
    settings = Settings.from_env()
    assert settings.whisper_model == "small"
    assert settings.whisper_device == "cpu"
    assert settings.whisper_compute_type == "int8"


def test_from_env_falls_back_when_whisper_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WHISPER_MODEL", raising=False)
    monkeypatch.delenv("WHISPER_DEVICE", raising=False)
    monkeypatch.delenv("WHISPER_COMPUTE_TYPE", raising=False)
    settings = Settings.from_env()
    assert settings.whisper_model == "medium"
    assert settings.whisper_device == "auto"
    assert settings.whisper_compute_type == "default"


def test_from_env_falls_back_on_blank_whisper_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHISPER_MODEL", "")
    monkeypatch.setenv("WHISPER_DEVICE", "   ")
    monkeypatch.setenv("WHISPER_COMPUTE_TYPE", "")
    settings = Settings.from_env()
    assert settings.whisper_model == "medium"
    assert settings.whisper_device == "auto"
    assert settings.whisper_compute_type == "default"


def test_default_embedding_model_is_multilingual_minilm() -> None:
    assert Settings().embedding_model == "paraphrase-multilingual-MiniLM-L12-v2"


def test_from_env_reads_embedding_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORACLE_EMBEDDING_MODEL", "another-model")
    assert Settings.from_env().embedding_model == "another-model"


def test_from_env_falls_back_when_embedding_model_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ORACLE_EMBEDDING_MODEL", raising=False)
    assert Settings.from_env().embedding_model == "paraphrase-multilingual-MiniLM-L12-v2"