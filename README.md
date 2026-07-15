# chorus

A discourse-synthesis satellite for [gather](https://github.com/HarperZ9/gather).
It reads a captured corpus of comments and threads and emits a weighted,
clustered, re-checkable reading of the discourse: what people are saying, and
which of it is worth reading. Zero third-party runtime dependencies.

Sentiment weights and ranks discourse; it is never an accept gate. Every digest
carries a receipt a stranger can re-run.

```bash
chorus run <corpus>            # a corpus -> a verified discourse digest
chorus corpora <root>          # discover gather corpora as discourse sources
chorus watch add <corpus>      # add a corpus to the daemon watchlist
chorus daemon --interval 300   # poll the watchlist, synthesize on change
chorus digests <store>         # what the daemon has synthesized
chorus mcp                     # the MCP stdio surface (chorus.run/corpora/digests/status/doctor)
```

Add `--model "<cmd>"` to `run` to overlay a model's read on the lexicon-uncertain
comments; the overlay is provenance-tagged and never enters the re-checkable core.
