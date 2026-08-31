"""Rule-based PT-BR text normalization (AD-008): fillers, casing, punctuation.

Consumed by the real pipeline; swappable via the `Normalizer` seam. Applies to a
single transcription unit (one sentence) for v1 — no sentence splitting.
"""

import re
from abc import ABC, abstractmethod

_FILLER_PATTERN = re.compile(r"\b(?:tipo|né|então|ééé|um|uh)\b", re.IGNORECASE)
_WHITESPACE_PATTERN = re.compile(r"\s+")
_ENDING_PUNCTUATION = (".", "!", "?")


class Normalizer(ABC):
    """Cleans raw transcribed text into paste-ready PT-BR text."""

    @abstractmethod
    def normalize(self, text: str) -> str:
        """Return the normalized form of the given raw text."""


class RuleBasedNormalizer(Normalizer):
    """Deterministic rule-based PT-BR normalization.

    Removes the filler blacklist (docs/spec.md §9.2), collapses whitespace,
    capitalizes the first character, and appends an ending period when the text
    does not already end in `.`, `!`, or `?`.
    """

    FILLERS = ("tipo", "né", "então", "ééé", "um", "uh")

    def normalize(self, text: str) -> str:
        cleaned = _FILLER_PATTERN.sub("", text)
        cleaned = _WHITESPACE_PATTERN.sub(" ", cleaned).strip()
        if not cleaned:
            return ""
        cleaned = cleaned[0].upper() + cleaned[1:]
        if not cleaned.endswith(_ENDING_PUNCTUATION):
            cleaned += "."
        return cleaned
