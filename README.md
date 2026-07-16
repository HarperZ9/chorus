# chorus

Read a comment section the way you wish you could: not scrolled, but **synthesized**.

chorus takes a corpus of comments or threads and returns a weighted, clustered,
re-checkable reading of the discourse. It tells you the themes people are actually
voicing, ranks them by how much the crowd engaged and how strongly they felt, and
for each theme it surfaces the sharpest dissent instead of hiding it behind an
average. Every digest carries a receipt a stranger can re-run to get the same
answer. Zero third-party runtime dependencies.

It orbits [gather](https://github.com/HarperZ9/gather): gather captures the corpus
with provenance, chorus synthesizes the discourse on top of it.

## What you get

- **Themes, ranked.** Comments cluster into themes by what they say; each theme
  carries its size, an engagement-and-sentiment weight, a sentiment split, and the
  single highest-weight voice that disagrees with the majority.
- **A receipt, not a vibe.** `--verify` re-derives the whole digest from the inputs
  and confirms it. A tampered digest fails even if its own hash was recomputed to
  match. Sentiment is a *weight*, never a verdict.
- **Honest nulls.** A missing engagement signal is recorded as absent, never
  counted as a zero. A too-thin corpus says so. The lexicon's limits (English-only,
  literal, no sarcasm) are stated in the digest itself.
- **A daemon.** Point it at a watchlist and it re-synthesizes only when a corpus
  actually changes, storing each receipted digest by its own hash.
- **An MCP surface.** Drive it from any MCP host: `chorus.run`, `chorus.corpora`,
  `chorus.digests`, `chorus.status`, `chorus.doctor`.

## Run it

```bash
pip install -e .

chorus run <corpus> --verify        # a corpus -> a verified discourse digest
chorus corpora <root>               # discover gather corpora as discourse sources
chorus watch add <corpus>           # add a corpus to the daemon watchlist
chorus daemon --interval 300        # poll the watchlist, synthesize on change
chorus digests <store>              # what the daemon has synthesized
chorus mcp                          # the MCP stdio server
```

`<corpus>` is a gather corpus directory (a folder holding `catalog.jsonl`) or a
JSON list of rows. Add `--model "<command>"` to `run` to overlay a model's read on
the comments the lexicon is least sure about; the overlay is provenance-tagged and
never enters the re-checkable core.

## The receipt

The digest's `receipt` binds the inputs, the method, and the result. `verify`
re-runs the deterministic pipeline (score, cluster, weight) from the same corpus
and checks the hash, so a dishonest digest cannot pass. Any model overlay is listed
separately with its own provenance and is excluded from that check: the parts a
stranger can re-derive and the parts that are model opinion are kept distinct, on
the record.

## Design

The design and its two exposed defects-caught-in-review live in
[docs/superpowers/specs](docs/superpowers/specs). Sentiment is coarse by
construction and the digest says so; clustering is lexical, not semantic. chorus
tells you what it did and hands you the means to check it.

## License

Source-available under the Chorus Fair-Source License (see [LICENSE](LICENSE)):
read it, run it, build on it; commercial use that competes with the project is
reserved.
