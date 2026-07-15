"""Deterministic lexicon sentiment (VADER-lineage, zero-dep).

A compact valence lexicon plus negation, intensifier, caps, and punctuation rules.
Every score re-computes exactly from the text, so it is re-checkable; the vocab is
versioned and hashed. This is coarse by construction (no sarcasm, no context) and
the digest says so. Sentiment is a weight, never an accept gate.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass

from chorus.item import DiscourseItem

LEXICON_VERSION = "1"

# valence in [-3, 3]; a small honest seed set, extend deliberately (bump LEXICON_VERSION).
_LEXICON: dict[str, float] = {
    "good": 1.5, "great": 2.2, "wonderful": 2.7, "love": 2.5, "excellent": 2.7,
    "amazing": 2.6, "best": 2.4, "brilliant": 2.3, "beautiful": 2.3, "happy": 2.0,
    "insightful": 1.8, "helpful": 1.7, "clear": 1.0, "true": 1.0, "agree": 1.4,
    "bad": -1.5, "terrible": -2.5, "awful": -2.6, "hate": -2.6, "worst": -2.6,
    "stupid": -2.2, "wrong": -1.6, "boring": -1.7, "nonsense": -2.0, "sad": -1.6,
    "confused": -1.2, "disagree": -1.4, "fear": -1.8, "angry": -2.0, "empty": -1.3,
}
_INTENSIFIERS: dict[str, float] = {
    "very": 0.3, "really": 0.3, "so": 0.25, "extremely": 0.4, "incredibly": 0.4,
    "absolutely": 0.4, "totally": 0.3, "quite": 0.15, "somewhat": -0.15, "slightly": -0.2,
}
_NEGATORS = {"not", "no", "never", "none", "cannot", "cant", "n't", "without", "hardly"}
_TOKEN = re.compile(r"[a-z']+|[!?]+", re.IGNORECASE)


def lexicon_vocab_sha() -> str:
    blob = "|".join(f"{k}:{v}" for k, v in sorted(_LEXICON.items()))
    return hashlib.sha256((LEXICON_VERSION + "\n" + blob).encode("utf-8")).hexdigest()[:16]


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text)


def score_text(text: str) -> tuple[float, tuple[str, ...]]:
    """Return (compound in [-1,1], firing valence tokens). Pure and deterministic."""
    toks = _tokens(text)
    total = 0.0
    firing: list[str] = []
    for i, tok in enumerate(toks):
        low = tok.lower()
        if low not in _LEXICON:
            continue
        val = _LEXICON[low]
        # caps emphasis: an all-caps valence word (not a 1-letter token) intensifies.
        if tok.isupper() and len(tok) > 1:
            val *= 1.25
        # look back up to 3 tokens for intensifiers and negation.
        for j in range(max(0, i - 3), i):
            w = toks[j].lower()
            if w in _INTENSIFIERS:
                val *= (1 + _INTENSIFIERS[w]) if val > 0 else (1 - _INTENSIFIERS[w])
            if w in _NEGATORS:
                val *= -0.74
        total += val
        firing.append(low)
    # exclamation emphasis
    total *= 1.0 + 0.05 * min(text.count("!"), 4)
    compound = total / math.sqrt(total * total + 15.0)  # squash to (-1, 1), VADER-style alpha
    return round(compound, 4), tuple(firing)


@dataclass(frozen=True)
class Scored:
    item: DiscourseItem
    compound: float
    provenance: str
    evidence: tuple[str, ...]


def score(items: list[DiscourseItem]) -> list[Scored]:
    out = []
    for it in items:
        compound, firing = score_text(it.text)
        out.append(Scored(item=it, compound=compound, provenance="lexicon", evidence=firing))
    return out
