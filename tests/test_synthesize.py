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


def test_digest_surfaces_engagement_coverage_and_coarseness():
    it_present = DiscourseItem("a", "video", "v", None, "x", "great sound", 12, None,
                               {"engagement_present": True})
    it_absent = DiscourseItem("b", "video", "v", None, "y", "bad sound", 0, None,
                              {"engagement_present": False})
    d = synthesize([Scored(it_present, 0.5, "lexicon", ()), Scored(it_absent, -0.5, "lexicon", ())])
    assert d.method["engagement_coverage"] == {"present": 1, "total": 2}
    assert "English-only" in d.method["coarseness"] and "never a verdict" in d.method["coarseness"]


def test_mixed_target_corpus_is_labelled_mixed_not_the_first_row():
    a = Scored(DiscourseItem("a", "video", "vid1", None, "x", "hi there", 0, None, {}), 0.0, "lexicon", ())
    b = Scored(DiscourseItem("b", "reddit", "post9", None, "y", "hi there", 0, None, {}), 0.0, "lexicon", ())
    d = synthesize([a, b])
    assert d.responds_to == "(mixed)" and d.method["distinct_targets"] == 2


def test_non_latin_text_forms_terms_and_does_not_crash():
    scored = [_s("这个视频很好 sound design", 3, 0.2, "a"), _s("这个视频很好 sound design", 2, 0.2, "b")]
    d = synthesize(scored, threshold=0.1)
    assert d.n_items == 2 and len(d.themes) == 1     # shared non-Latin + Latin terms cluster them
