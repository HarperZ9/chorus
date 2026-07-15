# chorus

A discourse-synthesis satellite for [gather](https://github.com/HarperZ9/gather).
It reads a captured corpus of comments and threads and emits a weighted,
clustered, re-checkable reading of the discourse: what people are saying, and
which of it is worth reading. Zero third-party runtime dependencies.

Sentiment weights and ranks discourse; it is never an accept gate. Every digest
carries a receipt a stranger can re-run.

```bash
chorus run <corpus-dir-or-items.json>
```
