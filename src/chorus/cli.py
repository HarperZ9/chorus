"""chorus CLI. Phase 1: `chorus run <corpus>` emits a discourse digest as JSON."""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys

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
    rows = _load_rows(args.path)
    scored = score(normalize(rows))
    digest = synthesize(scored)
    out = _digest_to_dict(digest)
    if args.verify:
        out["verified"] = verify_digest(digest, scored)
    print(json.dumps(out, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chorus")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="synthesize a discourse digest from a corpus")
    run.add_argument("path", help="a JSON file of gather-style rows, or a gather corpus directory")
    run.add_argument("--verify", action="store_true", help="re-derive and confirm the receipt")
    run.set_defaults(func=_cmd_run)
    args = parser.parse_args(argv)
    return args.func(args)
