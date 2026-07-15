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
from collections import Counter
from dataclasses import dataclass

from chorus.sentiment import Scored

_WORD = re.compile(r"[a-z0-9']+")
_STOP = set("the a an and or but of to in on for is are was were be been it this that "
            "i you he she they we my your with as at by from so not no".split())


def item_weight(engagement: int, compound: float, *, k: float = 0.5) -> float:
    return math.log1p(max(0, engagement)) * (1 + k * abs(compound))


def _terms(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2]


def _bucket(term: str, dims: int) -> int:
    return int(hashlib.md5(term.encode("utf-8")).hexdigest(), 16) % dims


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
    """Single-link connected components over hashed-TF-IDF cosine. Deterministic partition."""
    n = len(scored)
    if n == 0:
        return []
    df: dict[str, int] = {}
    for s in scored:
        for t in set(_terms(s.item.text)):
            df[t] = df.get(t, 0) + 1
    idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
    vecs = [_vector(s.item.text, idf, dims) for s in scored]
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            if _cosine(vecs[i], vecs[j]) >= threshold:
                parent[find(i)] = find(j)
    groups: dict[int, list[Scored]] = {}
    for idx, s in enumerate(scored):        # input order preserved within a group
        groups.setdefault(find(idx), []).append(s)
    return list(groups.values())


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


@dataclass(frozen=True)
class Digest:
    responds_to: str
    n_items: int
    themes: tuple[Theme, ...]
    method: dict
    receipt: object = None    # DigestReceipt; set by synthesize()


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
    )


def synthesize(scored: list[Scored], *, k: float = 0.5, threshold: float = 0.18,
               dims: int = 512, pos_cut: float = 0.1, neg_cut: float = -0.1) -> Digest:
    responds_to = scored[0].item.responds_to if scored else ""
    groups = cluster(scored, threshold=threshold, dims=dims)
    themes = [_build_theme(g, k=k, pos_cut=pos_cut, neg_cut=neg_cut) for g in groups]
    themes.sort(key=lambda t: t.weighted_score, reverse=True)
    digest = Digest(
        responds_to=responds_to, n_items=len(scored), themes=tuple(themes),
        method={"weight_k": k, "cluster_threshold": threshold, "dims": dims,
                "pos_cut": pos_cut, "neg_cut": neg_cut},
    )
    from chorus.receipt import build_receipt
    return dataclasses.replace(digest, receipt=build_receipt(scored, digest))
