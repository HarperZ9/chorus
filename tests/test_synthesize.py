from chorus.item import DiscourseItem
from chorus.sentiment import Scored
from chorus.synthesize import synthesize, Digest, Theme


def _s(text, eng, compound, i):
    it = DiscourseItem(i, "video", "vid", None, "a", text, eng, None, {})
    return Scored(it, compound, "lexicon", ())


def test_synthesize_builds_ranked_themes_with_distribution_and_dissent():
    scored = [
        _s("the audio mix sound design was great", 50, 0.6, "a"),
        _s("loved the sound design and audio", 10, 0.5, "b"),
        _s("actually the audio mixing was bad and muddy", 30, -0.5, "c"),
        _s("the plot story writing made no sense", 5, -0.4, "d"),
    ]
    d = synthesize(scored, threshold=0.12)
    assert isinstance(d, Digest) and d.responds_to == "vid" and d.n_items == 4
    assert d.themes == tuple(sorted(d.themes, key=lambda t: -t.weighted_score))
    audio = max(d.themes, key=lambda t: t.size)
    assert audio.size == 3
    assert 0.0 <= audio.sentiment["pos"] <= 1.0
    # a minority negative voice exists in a majority-positive theme -> dissent surfaced
    assert audio.dissent == "c"
    # representative is the highest-weight item (engagement 50)
    assert audio.representative == "a"


def test_theme_with_no_minority_has_no_dissent():
    scored = [_s("great", 5, 0.6, "a"), _s("great wonderful", 5, 0.6, "b")]
    d = synthesize(scored, threshold=0.0)
    assert d.themes[0].dissent is None
