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