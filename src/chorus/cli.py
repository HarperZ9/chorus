"""chorus CLI. Phase 1: `chorus run <corpus>` emits a discourse digest as JSON."""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import sys

_SHA256 = re.compile(r"[0-9a-f]{64}")

from chorus.item import normalize
from chorus.sentiment import score
from chorus.synthesize import synthesize
from chorus.receipt import verify as verify_digest


def _load_rows(path: str) -> list[dict]:
    if os.path.isdir(path):
        return _load_corpus_dir(path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_corpus_dir(path: str) -> list[dict]:
    """Load a gather corpus dir: catalog.jsonl rows, comment text from objects/<sha[:2]>/<sha[2:]>."""
    rows = []
    cat = os.path.join(path, "catalog.jsonl")
    with open(cat, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("kind") != "comment":
                continue
            sha = r.get("sha256", "")
            if _SHA256.fullmatch(sha):      # never build a read path from an unvalidated field
                obj = os.path.join(path, "objects", sha[:2], sha[2:])
                if os.path.exists(obj):
                    with open(obj, encoding="utf-8") as of:
                        r["text"] = of.read()
            rows.append(r)
    return rows


def _digest_to_dict(digest) -> dict:
    return dataclasses.asdict(digest)


def _cmd_run(args) -> int:
    if not os.path.exists(args.path):
        print(f"chorus: not found: {args.path}", file=sys.stderr)
        return 1
    try:
        rows = _load_rows(args.path)
    except (json.JSONDecodeError, OSError) as e:
        print(f"chorus: could not read corpus {args.path}: {e}", file=sys.stderr)
        return 1
    if not isinstance(rows, list):
        print("chorus: corpus JSON must be a list of rows", file=sys.stderr)
        return 1
    scored = score(normalize(rows))
    digest = synthesize(scored)
    out = _digest_to_dict(digest)
    if args.verify:
        out["verified"] = verify_digest(digest, scored)
    print(json.dumps(out, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def _cmd_corpora(args) -> int:
    from chorus.corpora import list_corpora
    out = list_corpora(args.root)
    print(json.dumps(out, indent=2, sort_keys=True, ensure_ascii=False))
    return 1 if "error" in out else 0


def main(argv: list[str] | None = None) -> int:
    # Emit UTF-8 regardless of the console/redirect codepage: a digest of real comments carries
    # emoji and non-Latin text, which would crash a cp1252 stdout on Windows. Guarded because a
    # capture stream (pytest capsys) has no reconfigure().
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="chorus")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="synthesize a discourse digest from a corpus")
    run.add_argument("path", help="a JSON file of gather-style rows, or a gather corpus directory")
    run.add_argument("--verify", action="store_true", help="re-derive and confirm the receipt")
    run.set_defaults(func=_cmd_run)
    corpora = sub.add_parser("corpora", help="discover gather corpora under a root as discourse sources")
    corpora.add_argument("root", help="a directory to scan for gather corpora (dirs holding catalog.jsonl)")
    corpora.set_defaults(func=_cmd_corpora)
    args = parser.parse_args(argv)
    return args.func(args)
