"""Weighting and clustering for the discourse digest.

Weight combines engagement (damped) with sentiment intensity. Clustering is a
zero-dep, deterministic hashed-TF-IDF cosine over connected components, so themes
re-derive identically. The synthesize() entry point turns clusters into a Digest.
"""
from __future__ import annotations

import dataclasses
import hashlib
import math
import re
import statistics
from collections import Counter
from dataclasses import dataclass

from chorus.sentiment import Scored

_WORD = re.compile(r"\w+", re.UNICODE)   # Unicode-aware so non-Latin corpora still form term vectors
_STOP = set("the a an and or but of to in on for is are was were be been it this that "
            "i you he she they we my your with as at by from so not no".split())


def item_weight(engagement: int, compound: float, *, k: float = 0.5) -> float:
    return math.log1p(max(0, engagement)) * (1 + k * abs(compound))


def _terms(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2]


def _bucket(term: str, dims: int) -> int:
    # feature bucketing, not security; usedforsecurity=False keeps it working under FIPS mode.
    return int(hashlib.md5(term.encode("utf-8"), usedforsecurity=False).hexdigest(), 16) % dims


def _vector(text: str, idf: dict[str, float], dims: int) -> dict[int, float]:
    tf: dict[str, int] = {}
    for t in _terms(text):
        tf[t] = tf.get(t, 0) + 1
    vec: dict[int, float] = {}
    for t, c in tf.items():
        vec[_bucket(t, dims)] = vec.get(_bucket(t, dims), 0.0) + c * idf.get(t, 1.0)
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {b: v / norm for b, v in vec.items()}


def _cosine(a: dict[int, float], b: dict[int, float]) -> float:
    small, big = (a, b) if len(a) <= len(b) else (b, a)
    return sum(v * big.get(k, 0.0) for k, v in small.items())


def cluster(scored: list[Scored], *, threshold: float = 0.18, dims: int = 512) -> list[list[Scored]]:
    """Leader (greedy nearest-leader) clustering over hashed-TF-IDF cosine.

    An item joins the existing leader it is MOST similar to (>= threshold), or starts a new
    cluster. Unlike single-link connected components, membership requires similarity to a
    cluster's LEADER, not a transitive chain of pairwise links, so large diverse corpora do not
    collapse into one megacluster. Deterministic: leaders are seeded in (engagement desc, input
    index) order, so the most-engaged comments anchor the themes; members keep input order.
    """
    n = len(scored)
    if n == 0:
        return []
    df: dict[str, int] = {}
    for s in scored:
        for t in set(_terms(s.item.text)):
            df[t] = df.get(t, 0) + 1
    idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
    vecs = [_vector(s.item.text, idf, dims) for s in scored]
    order = sorted(range(n), key=lambda i: (-scored[i].item.engagement, i))
    leaders: list[dict[int, float]] = []      # leader vectors, in creation order
    members: list[list[int]] = []             # original indices per leader
    for i in order:
        best, best_sim = -1, threshold
        for li, lvec in enumerate(leaders):
            sim = _cosine(vecs[i], lvec)
            if sim >= best_sim:
                best, best_sim = li, sim
        if best < 0:
            leaders.append(vecs[i])
            members.append([i])
        else:
            members[best].append(i)
    return [[scored[i] for i in sorted(m)] for m in members]


@dataclass(frozen=True)
class Theme:
    label: str
    terms: tuple[str, ...]
    size: int
    weighted_score: float
    sentiment: dict
    representative: str
    dissent: str | None
    item_ids: tuple[str, ...]
    # How contested the theme is: the population standard deviation of its members'
    # compound sentiment, in [0, 1]. 0 is consensus (everyone agrees, however strongly);
    # it approaches 1 as voices split hard between +1 and -1. It reads out how divided
    # AND how strongly felt a theme is, so the valuable debate can be surfaced, not just
    # the loudest agreement. Re-derivable (folded into the receipt); never a verdict.
    controversy: float = 0.0


@dataclass(frozen=True)
class Digest:
    responds_to: str
    n_items: int
    themes: tuple[Theme, ...]
    method: dict
    # Aspect-level contestedness: the topics the corpus is genuinely SPLIT on, ranked.
    # It is measured across every item mentioning a term, so it survives the lexical
    # clustering that separates positive and negative wording about the same topic into
    # different themes. Each row: {term, mentions, pos, neg, contested}. Re-derivable.
    contested: tuple = ()
    receipt: object = None    # DigestReceipt; set by synthesize()
    # An optional model-sentiment overlay: advisory, provenance-tagged model opinion on the
    # lexicon-uncertain items. Deliberately NOT part of digest_body_sha, so it never changes the
    # re-checkable core; the receipt's model_ref names the model that produced it.
    model_layer: tuple = ()


def _label(group, top_terms):
    return " / ".join(top_terms[:3]) if top_terms else "(untitled theme)"


def _build_theme(group, *, k, pos_cut, neg_cut) -> Theme:
    weighted = [(s, item_weight(s.item.engagement, s.compound, k=k)) for s in group]
    term_counts = Counter(t for s in group for t in _terms(s.item.text))
    top_terms = [t for t, _ in term_counts.most_common(5)]
    pos = sum(1 for s in group if s.compound >= pos_cut)
    neg = sum(1 for s in group if s.compound <= neg_cut)
    neu = len(group) - pos - neg
    n = len(group)
    majority_pos = pos >= neg
    minority = [(s, w) for s, w in weighted
                if ((s.compound <= neg_cut) if majority_pos else (s.compound >= pos_cut))]
    dissent = max(minority, key=lambda sw: sw[1])[0].item.id if minority else None
    representative = max(weighted, key=lambda sw: sw[1])[0].item.id
    controversy = round(statistics.pstdev([s.compound for s in group]), 4) if n > 1 else 0.0
    return Theme(
        label=_label(group, top_terms),
        terms=tuple(top_terms),
        size=n,
        weighted_score=round(sum(w for _, w in weighted), 4),
        sentiment={"pos": round(pos / n, 3), "neg": round(neg / n, 3),
                   "neu": round(neu / n, 3),
                   "mean_compound": round(sum(s.compound for s in group) / n, 4)},
        representative=representative,
        dissent=dissent,
        item_ids=tuple(s.item.id for s in group),
        controversy=controversy,
    )


_COARSENESS = ("lexicon sentiment is English-only and literal (no sarcasm, irony, or context); "
               "clustering is lexical, not semantic. Sentiment is a weight, never a verdict.")

_ASPECT_MIN_MENTIONS = 3   # a term needs this many mentioning voices to be judged contested
_ASPECT_TOP_K = 12         # how many contested aspects the digest surfaces


def contested_aspects(scored: list[Scored], *, pos_cut: float, neg_cut: float,
                      min_mentions: int = _ASPECT_MIN_MENTIONS,
                      top_k: int = _ASPECT_TOP_K) -> tuple:
    """Aspect-level contestedness, immune to the lexical clustering that separates
    positive and negative wording about the same topic into different themes. For each
    salient term, gather EVERY item that mentions it and measure how split their
    sentiment is. A term qualifies only with real two-sided disagreement (at least one
    clearly positive AND one clearly negative voice); one-sided praise, one-sided
    complaint, or neutral chatter is excluded. Deterministic and re-derivable: ranked by
    contestedness (population stdev of the mentioning items' compound), then by how many
    voices weighed in, then by term."""
    buckets: dict[str, list[float]] = {}
    for s in scored:
        for t in set(_terms(s.item.text)):
            buckets.setdefault(t, []).append(s.compound)
    rows = []
    for t, comps in buckets.items():
        n = len(comps)
        if n < min_mentions:
            continue
        pos = sum(1 for c in comps if c >= pos_cut)
        neg = sum(1 for c in comps if c <= neg_cut)
        if pos < 1 or neg < 1:                 # not two-sided -> not contested
            continue
        rows.append({"term": t, "mentions": n,
                     "pos": round(pos / n, 3), "neg": round(neg / n, 3),
                     "contested": round(statistics.pstdev(comps), 4)})
    rows.sort(key=lambda r: (-r["contested"], -r["mentions"], r["term"]))
    return tuple(rows[:top_k])


def _responds_to(scored: list[Scored]) -> str:
    targets = {s.item.responds_to for s in scored}
    if not targets:
        return ""
    return next(iter(targets)) if len(targets) == 1 else "(mixed)"


def synthesize(scored: list[Scored], *, k: float = 0.5, threshold: float = 0.18,
               dims: int = 512, pos_cut: float = 0.1, neg_cut: float = -0.1,
               aspect_min_mentions: int = _ASPECT_MIN_MENTIONS, aspect_top_k: int = _ASPECT_TOP_K,
               model_scores: list[dict] | None = None, model_ref: str | None = None) -> Digest:
    groups = cluster(scored, threshold=threshold, dims=dims)
    themes = [_build_theme(g, k=k, pos_cut=pos_cut, neg_cut=neg_cut) for g in groups]
    themes.sort(key=lambda t: t.weighted_score, reverse=True)
    # Honest null surfaced in the digest itself: how many items actually carried an engagement
    # signal, how many distinct targets, and the method's coarseness. All hashed into the receipt.
    present = sum(1 for s in scored if s.item.meta.get("engagement_present"))
    digest = Digest(
        responds_to=_responds_to(scored), n_items=len(scored), themes=tuple(themes),
        method={"weight_k": k, "cluster_threshold": threshold, "dims": dims,
                "pos_cut": pos_cut, "neg_cut": neg_cut,
                "aspect_min_mentions": aspect_min_mentions, "aspect_top_k": aspect_top_k,
                "engagement_coverage": {"present": present, "total": len(scored)},
                "distinct_targets": len({s.item.responds_to for s in scored}),
                "coarseness": _COARSENESS},
        contested=contested_aspects(scored, pos_cut=pos_cut, neg_cut=neg_cut,
                                    min_mentions=aspect_min_mentions, top_k=aspect_top_k),
        model_layer=tuple(model_scores or ()),
    )
    from chorus.receipt import build_receipt
    return dataclasses.replace(digest, receipt=build_receipt(scored, digest, model_ref=model_ref))
