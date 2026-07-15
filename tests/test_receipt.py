import dataclasses
from chorus.item import DiscourseItem
from chorus.sentiment import score
from chorus.synthesize import synthesize
from chorus.receipt import verify


def _items():
    rows = [("a", "sound design great", 20), ("b", "great audio sound", 5),
            ("c", "story plot was bad", 8)]
    return [DiscourseItem(i, "video", "v", None, "au", t, e, None, {}) for i, t, e in rows]


def test_intact_digest_verifies():
    d = synthesize(score(_items()), threshold=0.1)
    assert d.receipt.digest_sha256 and d.receipt.model_ref is None
    assert verify(d, score(_items())) is True


def test_tampered_theme_fails_verification():
    scored = score(_items())
    d = synthesize(scored, threshold=0.1)
    forged_theme = dataclasses.replace(d.themes[0], weighted_score=999.0)
    forged = dataclasses.replace(d, themes=(forged_theme,) + d.themes[1:])
    assert verify(forged, scored) is False


def test_different_inputs_fail_verification():
    d = synthesize(score(_items()), threshold=0.1)
    other = _items()[:2]
    assert verify(d, score(other)) is False
