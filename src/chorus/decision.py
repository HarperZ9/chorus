"""Source-change decisions on top of Chorus's deterministic digest path.

This module compares two already-gathered source packs. It does not fetch or
publish anything. The public projection is intentionally narrow: item ids,
source refs, change counts, and hashes only, with no raw source text.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
from typing import Any

from chorus.item import DiscourseItem, normalize
from chorus.receipt import input_digest, verify as verify_digest
from chorus.sentiment import score
from chorus.synthesize import synthesize

SCHEMA = "chorus.source-decision/v1"
PUBLIC_SCHEMA = "chorus.public-source-decision/v1"
METHOD_VERSION = "chorus-source-decision/1"
_SHA256 = re.compile(r"[0-9a-f]{64}")


class SourceReadError(Exception):
    def __init__(self, code: str, message: str, *, path: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path


def _sha(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_rows(path: str, *, label: str) -> list[dict]:
    if not path or not os.path.exists(path):
        raise SourceReadError(f"missing_{label}", f"{label} source not found", path=path)
    try:
        if os.path.isdir(path):
            return _load_corpus_dir(path, label=label)
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
    except json.JSONDecodeError as exc:
        raise SourceReadError(f"invalid_{label}_json", f"{label} source is not valid JSON: {exc}", path=path)
    except OSError as exc:
        raise SourceReadError(f"read_{label}_failed", f"{label} source could not be read: {exc}", path=path)
    if not isinstance(rows, list):
        raise SourceReadError(f"invalid_{label}_shape", f"{label} source JSON must be a list of rows", path=path)
    return rows


def _load_corpus_dir(path: str, *, label: str) -> list[dict]:
    rows = []
    cat = os.path.join(path, "catalog.jsonl")
    if not os.path.exists(cat):
        raise SourceReadError(f"missing_{label}_catalog", f"{label} corpus directory has no catalog.jsonl", path=path)
    try:
        with open(cat, encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise SourceReadError(
                        f"invalid_{label}_jsonl",
                        f"{label} catalog.jsonl line {line_number} is not valid JSON: {exc}",
                        path=cat,
                    )
                if row.get("kind") == "comment":
                    sha = row.get("sha256", "")
                    if _SHA256.fullmatch(sha):
                        obj = os.path.join(path, "objects", sha[:2], sha[2:])
                        if os.path.exists(obj):
                            with open(obj, encoding="utf-8") as of:
                                row["text"] = of.read()
                rows.append(row)
    except OSError as exc:
        raise SourceReadError(f"read_{label}_failed", f"{label} corpus could not be read: {exc}", path=path)
    return rows


def _public_url(item: DiscourseItem) -> str | None:
    for key in ("source_url", "url", "permalink"):
        value = item.meta.get(key)
        if isinstance(value, str) and value.strip().lower().startswith(("http://", "https://")):
            return value.strip()
    return None


def _source_url_allowed(item: DiscourseItem) -> bool:
    return item.meta.get("public_projection_url_allowed") is True or item.meta.get("public_url_allowed") is True


def _source_ref(item: DiscourseItem) -> dict:
    out = {"id": item.id, "source": item.source, "responds_to": item.responds_to}
    url = _public_url(item)
    if url:
        out["source_url"] = url
    return out


def _fingerprint(item: DiscourseItem) -> dict:
    body = {
        "id": item.id,
        "source": item.source,
        "responds_to": item.responds_to,
        "parent": item.parent,
        "engagement": item.engagement,
        "engagement_present": bool(item.meta.get("engagement_present")),
        "source_url": _public_url(item),
        "text_sha256": _text_sha(item.text),
    }
    body["item_sha256"] = _sha(body)
    body["source_url_allowed"] = _source_url_allowed(item)
    return body


def _snapshot(items: list[DiscourseItem], *, label: str) -> tuple[dict[str, dict], list[dict]]:
    by_id: dict[str, dict] = {}
    failures: list[dict] = []
    for item in items:
        if not item.id:
            failures.append({"code": f"missing_{label}_item_id", "message": f"{label} contains an item with no id"})
            continue
        if item.id in by_id:
            failures.append({"code": f"duplicate_{label}_item_id", "message": f"{label} repeats item id {item.id}"})
            continue
        fp = _fingerprint(item)
        fp["ref"] = _source_ref(item)
        by_id[item.id] = fp
    return by_id, failures


def _changed_fields(current: dict, reference: dict) -> list[str]:
    keys = ("source", "responds_to", "parent", "engagement", "engagement_present", "source_url", "text_sha256")
    return [key for key in keys if current.get(key) != reference.get(key)]


def _change_entry(snapshot: dict) -> dict:
    return {
        "id": snapshot["id"],
        "source": snapshot["source"],
        "responds_to": snapshot["responds_to"],
        "source_url": snapshot.get("source_url"),
        "source_url_allowed": bool(snapshot.get("source_url_allowed")),
        "text_sha256": snapshot["text_sha256"],
        "item_sha256": snapshot["item_sha256"],
    }


def _changed_entry(current: dict, reference: dict) -> dict:
    return {
        "id": current["id"],
        "changed_fields": _changed_fields(current, reference),
        "current": _change_entry(current),
        "reference": _change_entry(reference),
    }


def _digest_outline(digest: dict) -> dict:
    return {
        "responds_to": digest["responds_to"],
        "n_items": digest["n_items"],
        "themes": [
            {
                "label": theme["label"],
                "size": theme["size"],
                "item_ids": list(theme["item_ids"]),
                "dissent": theme["dissent"],
                "controversy": theme["controversy"],
            }
            for theme in digest["themes"][:8]
        ],
        "contested": list(digest.get("contested", ())),
        "method": digest["method"],
        "receipt": digest["receipt"],
    }


def _public_ref(row: dict) -> dict:
    out = {"id": row["id"], "source": row["source"], "responds_to": row["responds_to"]}
    if row.get("source_url_allowed") and row.get("source_url"):
        out["source_url"] = row["source_url"]
    out["text_sha256"] = row["text_sha256"]
    out["item_sha256"] = row["item_sha256"]
    return out


def _public_receipt(receipt: dict | None) -> dict | None:
    if not receipt:
        return None
    return {
        "method_version": receipt["method_version"],
        "task_sha256": receipt["task_sha256"],
        "current_input_sha256": receipt["current_input_sha256"],
        "reference_input_sha256": receipt["reference_input_sha256"],
        "current_fingerprint_sha256": receipt["current_fingerprint_sha256"],
        "reference_fingerprint_sha256": receipt["reference_fingerprint_sha256"],
        "status": receipt["status"],
        "decision_sha256": receipt["decision_sha256"],
    }


def _public_projection(result: dict) -> dict:
    changes = result.get("changes", {})
    return {
        "schema": PUBLIC_SCHEMA,
        "task": result.get("task", ""),
        "status": result["status"],
        "decision": result["decision"],
        "human_summary": result["human_summary"],
        "source_counts": result.get("source_counts", {}),
        "changes": {
            "counts": changes.get("counts", {"added": 0, "removed": 0, "changed": 0, "unchanged": 0}),
            "added": [_public_ref(row) for row in changes.get("added", [])],
            "removed": [_public_ref(row) for row in changes.get("removed", [])],
            "changed": [
                {
                    "id": row["id"],
                    "changed_fields": row["changed_fields"],
                    "current": _public_ref(row["current"]),
                    "reference": _public_ref(row["reference"]),
                }
                for row in changes.get("changed", [])
            ],
        },
        "checks": result.get("checks", {}),
        "source_failures": [
            {"code": failure["code"], "message": failure["message"]}
            for failure in result.get("source_failures", [])
        ],
        "receipt": _public_receipt(result.get("receipt")),
        "limitations": [
            "Public projection excludes raw source text, author names, local paths, private session content, and bulk comments.",
            "MATCH only means the compared source ids and fingerprints matched; it does not prove the source set is complete.",
            "DRIFT identifies source changes for review; it does not decide product readiness by itself.",
        ],
    }


def _failure_result(task: str, failures: list[dict], *, current_path: str | None = None,
                    reference_path: str | None = None) -> dict:
    result = {
        "schema": SCHEMA,
        "ok": False,
        "task": task,
        "status": "UNVERIFIABLE",
        "decision": "hold_for_source_repair",
        "inputs": {"current": current_path, "reference": reference_path},
        "source_counts": {"current_rows": 0, "reference_rows": 0, "current_items": 0, "reference_items": 0},
        "changes": {"counts": {"added": 0, "removed": 0, "changed": 0, "unchanged": 0},
                    "added": [], "removed": [], "changed": []},
        "checks": {"current_digest_verified": False, "reference_digest_verified": False},
        "source_failures": failures,
        "human_summary": "Source comparison is unverifiable; repair the listed source failure before using it.",
        "receipt": None,
    }
    result["public_projection"] = _public_projection(result)
    return result


def build_decision(current_rows: list[dict], reference_rows: list[dict], *, task: str = "") -> dict:
    failures: list[dict] = []
    if not isinstance(current_rows, list):
        failures.append({"code": "invalid_current_shape", "message": "current source must be a list of rows"})
    if not isinstance(reference_rows, list):
        failures.append({"code": "invalid_reference_shape", "message": "reference source must be a list of rows"})
    if failures:
        return _failure_result(task, failures)

    current_items = normalize(current_rows)
    reference_items = normalize(reference_rows)
    if not current_items:
        failures.append({"code": "empty_current_discourse", "message": "current source has no discourse rows"})
    if not reference_items:
        failures.append({"code": "empty_reference_discourse", "message": "reference source has no discourse rows"})

    current_snapshot, current_failures = _snapshot(current_items, label="current")
    reference_snapshot, reference_failures = _snapshot(reference_items, label="reference")
    failures.extend(current_failures)
    failures.extend(reference_failures)
    if failures:
        result = _failure_result(task, failures)
        result["source_counts"] = {
            "current_rows": len(current_rows),
            "reference_rows": len(reference_rows),
            "current_items": len(current_items),
            "reference_items": len(reference_items),
        }
        result["public_projection"] = _public_projection(result)
        return result

    current_scored = score(current_items)
    reference_scored = score(reference_items)
    current_digest = synthesize(current_scored)
    reference_digest = synthesize(reference_scored)
    current_digest_dict = dataclasses.asdict(current_digest)
    reference_digest_dict = dataclasses.asdict(reference_digest)

    current_ids = set(current_snapshot)
    reference_ids = set(reference_snapshot)
    added = [_change_entry(current_snapshot[item_id]) for item_id in sorted(current_ids - reference_ids)]
    removed = [_change_entry(reference_snapshot[item_id]) for item_id in sorted(reference_ids - current_ids)]
    changed = [
        _changed_entry(current_snapshot[item_id], reference_snapshot[item_id])
        for item_id in sorted(current_ids & reference_ids)
        if current_snapshot[item_id]["item_sha256"] != reference_snapshot[item_id]["item_sha256"]
    ]
    unchanged = sorted(
        item_id for item_id in current_ids & reference_ids
        if current_snapshot[item_id]["item_sha256"] == reference_snapshot[item_id]["item_sha256"]
    )
    status = "DRIFT" if added or removed or changed else "MATCH"
    decision = "review_current_sources" if status == "DRIFT" else "source_set_unchanged"
    changes = {
        "counts": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "unchanged": len(unchanged),
        },
        "added": added,
        "removed": removed,
        "changed": changed,
    }
    receipt_body = {
        "method_version": METHOD_VERSION,
        "task_sha256": _text_sha(task),
        "current_input_sha256": input_digest(current_scored),
        "reference_input_sha256": input_digest(reference_scored),
        "current_fingerprint_sha256": _sha(current_snapshot),
        "reference_fingerprint_sha256": _sha(reference_snapshot),
        "changes": changes,
        "status": status,
    }
    receipt = {**receipt_body, "decision_sha256": _sha(receipt_body)}
    result = {
        "schema": SCHEMA,
        "ok": True,
        "task": task,
        "status": status,
        "decision": decision,
        "inputs": {},
        "source_counts": {
            "current_rows": len(current_rows),
            "reference_rows": len(reference_rows),
            "current_items": len(current_items),
            "reference_items": len(reference_items),
            "comparable_ids": len(current_ids | reference_ids),
        },
        "changes": changes,
        "checks": {
            "current_digest_verified": verify_digest(current_digest, current_scored),
            "reference_digest_verified": verify_digest(reference_digest, reference_scored),
            "current_input_sha256": input_digest(current_scored),
            "reference_input_sha256": input_digest(reference_scored),
        },
        "disagreement": {
            "current": _digest_outline(current_digest_dict),
            "reference": _digest_outline(reference_digest_dict),
        },
        "source_failures": [],
        "receipt": receipt,
        "human_summary": (
            f"Source comparison detected {len(added)} added, {len(removed)} removed, "
            f"and {len(changed)} changed item(s) across {len(current_ids | reference_ids)} comparable ids; "
            f"{'review current sources before release decision.' if status == 'DRIFT' else 'no source drift was detected.'}"
        ),
    }
    result["public_projection"] = _public_projection(result)
    return result


def decision_from_paths(current: str, reference: str, *, task: str = "") -> dict:
    failures: list[dict] = []
    current_rows: list[dict] | None = None
    reference_rows: list[dict] | None = None
    for label, path in (("current", current), ("reference", reference)):
        try:
            rows = _load_rows(path, label=label)
        except SourceReadError as exc:
            failure = {"code": exc.code, "message": exc.message}
            if exc.path:
                failure["path"] = exc.path
            failures.append(failure)
            continue
        if label == "current":
            current_rows = rows
        else:
            reference_rows = rows
    if failures:
        result = _failure_result(task, failures, current_path=current, reference_path=reference)
        current_items = normalize(current_rows) if isinstance(current_rows, list) else []
        reference_items = normalize(reference_rows) if isinstance(reference_rows, list) else []
        result["source_counts"] = {
            "current_rows": len(current_rows) if isinstance(current_rows, list) else 0,
            "reference_rows": len(reference_rows) if isinstance(reference_rows, list) else 0,
            "current_items": len(current_items),
            "reference_items": len(reference_items),
        }
        result["public_projection"] = _public_projection(result)
        return result
    assert current_rows is not None and reference_rows is not None
    result = build_decision(current_rows, reference_rows, task=task)
    result["inputs"] = {"current": current, "reference": reference}
    result["public_projection"] = _public_projection(result)
    return result
