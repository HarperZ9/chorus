# Changelog

## Unreleased

- Adds `chorus decision` and MCP `chorus.decision`, a source-change review gate
  that compares current and reference gather-style source packs, reports
  added/removed/changed/unchanged item ids, verifies both deterministic Chorus
  digests, and returns typed `UNVERIFIABLE` failure states for missing, malformed,
  empty, or ambiguous source inputs.
- Adds an allowlisted public projection for the review-gate result. It keeps counts,
  ids, explicitly allowed source refs, hashes, receipts, and limitations while
  excluding raw source text, author names, local paths, private sessions, and bulk
  comments.

## 0.2.0 - 2026-09-07

- Adds deterministic corpus-salience theme labels with `label_quality` support metadata so weak and singleton labels are visible in the digest.
- Writes new receipts as `chorus-lens/3`, binding label terms and `label_quality` into the re-checkable digest body.
- Preserves historical `chorus-lens/2` verification through an explicit legacy verifier. v2 receipts verify against the v2 body shape and do not bind the current v3-only `terms` and `label_quality` fields.
- Fixes receipt verification so the submitted digest body must match its receipt before the verifier accepts a re-derived body.

This release does not claim better semantic insight from comment corpora. It reduces generic-label false success on the included controls and labels weak support, while lexical clustering remains a known limitation.

## 0.1.0

- Initial discourse synthesis package with CLI, MCP stdio surface, daemon, deterministic sentiment, lexical clustering, contested aspects, and re-checkable receipts.
