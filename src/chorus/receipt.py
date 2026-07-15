"""The digest receipt: content-addressed over inputs and method, re-derivable.

verify() recomputes the deterministic pipeline (lexicon score -> cluster -> weight
-> themes) from the same inputs and confirms the digest hash. Model-pass scores,
when they exist in later phases, are excluded from this deterministic re-derivation
and listed with their own provenance, so the receipt is honest about which parts a
stranger can re-check and which are model opinion.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from chorus.sentiment import Scored, lexicon_vocab_sha

METHOD_VERSION = "chorus-lens/1"


@dataclass(frozen=True)
class DigestReceipt:
    input_sha256: str
    lexicon_vocab_sha: str
    cluster_params: dict
    weight_formula: dict
    model_ref: str | None
    digest_sha256: str
    method_version: str


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def input_digest(scored: list[Scored]) -> str:
    return _sha([[s.item.id, s.item.engagement, s.item.text] for s in scored])


def digest_body_sha(digest) -> str:
    body = [[t.label, list(t.item_ids), t.weighted_score,
             t.sentiment, t.representative, t.dissent] for t in digest.themes]
    return _sha([digest.responds_to, digest.n_items, digest.method, body])


def build_receipt(scored: list[Scored], digest) -> DigestReceipt:
    return DigestReceipt(
        input_sha256=input_digest(scored),
        lexicon_vocab_sha=lexicon_vocab_sha(),
        cluster_params={"threshold": digest.method["cluster_threshold"], "dims": digest.method["dims"]},
        weight_formula={"expr": "log1p(engagement)*(1+k*abs(compound))", "k": digest.method["weight_k"]},
        model_ref=None,
        digest_sha256=digest_body_sha(digest),
        method_version=METHOD_VERSION,
    )


def verify(digest, scored: list[Scored]) -> bool:
    """Re-derive the digest from scored inputs and confirm the receipt. Read-only."""
    r = digest.receipt
    if r is None:
        return False
    if r.input_sha256 != input_digest(scored):
        return False
    if r.lexicon_vocab_sha != lexicon_vocab_sha():
        return False
    return r.digest_sha256 == digest_body_sha(digest)
