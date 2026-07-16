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


def test_tampered_theme_fails_even_when_receipt_hash_is_recomputed():
    """A real forger recomputes the receipt hash to match the tampered body. verify must still
    catch it, because it re-derives the digest from the INPUTS, not from the digest's own stored
    hash. This is the whole value of the receipt."""
    from chorus.receipt import digest_body_sha
    scored = score(_items())
    d = synthesize(scored, threshold=0.1)
    lie = dataclasses.replace(d.themes[0], weighted_score=999.0, label="everyone loved it")
    forged = dataclasses.replace(d, themes=(lie,) + d.themes[1:])
    forged = dataclasses.replace(
        forged, receipt=dataclasses.replace(forged.receipt, digest_sha256=digest_body_sha(forged)))
    assert verify(forged, scored) is False


def test_tampered_controversy_fails_verification():
    """controversy is part of the re-derivable body: a forged controversy that recomputes
    its own receipt hash is still caught, because verify re-derives it from the inputs."""
    from chorus.receipt import digest_body_sha
    scored = score(_items())
    d = synthesize(scored, threshold=0.1)
    lie = dataclasses.replace(d.themes[0], controversy=0.999)
    forged = dataclasses.replace(d, themes=(lie,) + d.themes[1:])
    forged = dataclasses.replace(
        forged, receipt=dataclasses.replace(forged.receipt, digest_sha256=digest_body_sha(forged)))
    assert verify(forged, scored) is False


def test_tampered_contested_aspect_fails_verification():
    """The aspect-contestedness list is part of the re-derivable body: forging a row's
    split score and recomputing the receipt hash is still caught, because verify
    re-derives the contested aspects from the inputs."""
    from chorus.receipt import digest_body_sha
    rows = [("a", "the battery is amazing", 5), ("b", "the battery is amazing", 5),
            ("c", "the battery is terrible awful", 8), ("d", "battery so bad", 4)]
    items = [DiscourseItem(i, "video", "v", None, "au", t, e, None, {}) for i, t, e in rows]
    scored = score(items)
    d = synthesize(scored, threshold=0.1)
    assert d.contested, "fixture should produce at least one contested aspect"
    lie = dict(d.contested[0]); lie["contested"] = 0.999; lie["neg"] = 0.0
    forged = dataclasses.replace(d, contested=(lie,) + d.contested[1:])
    forged = dataclasses.replace(
        forged, receipt=dataclasses.replace(forged.receipt, digest_sha256=digest_body_sha(forged)))
    assert verify(forged, scored) is False


def test_changed_method_version_fails_verification():
    scored = score(_items())
    d = synthesize(scored, threshold=0.1)
    stale = dataclasses.replace(d, receipt=dataclasses.replace(d.receipt, method_version="chorus-lens/0"))
    assert verify(stale, scored) is False


def test_caller_supplied_fake_sentiment_is_ignored_by_reverification():
    """verify re-scores sentiment from the item text, so a caller cannot make an honest digest
    verify against fabricated compound values (nor forge one that way)."""
    scored = score(_items())
    d = synthesize(scored, threshold=0.1)
    faked = [dataclasses.replace(s, compound=0.99) for s in scored]  # lie about sentiment
    assert verify(d, faked) is True   # re-derivation ignores the caller's compound, uses text


def test_different_inputs_fail_verification():
    d = synthesize(score(_items()), threshold=0.1)
    other = _items()[:2]
    assert verify(d, score(other)) is False


def test_digest_hash_is_pinned_for_a_fixed_input():
    """A hard-coded expected hash pins cross-process determinism: a PYTHONHASHSEED-style regression
    or any silent change to the scoring/clustering/weighting path breaks this."""
    from chorus.item import normalize
    rows = [{"kind": "comment", "id": "a", "ref": "v", "text": "great sound design", "meta": {"like_count": 20}},
            {"kind": "comment", "id": "b", "ref": "v", "text": "loved the sound design", "meta": {"like_count": 3}},
            {"kind": "comment", "id": "c", "ref": "v", "text": "the plot was bad", "meta": {"like_count": 9}}]
    d = synthesize(score(normalize(rows)))
    assert d.receipt.digest_sha256 == "d2dc18d6979ec74c252bbca67f0b0a906906c5aa30f92fa7cb5d346e62178f66"
