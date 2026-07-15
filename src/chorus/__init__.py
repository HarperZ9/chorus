"""chorus — a discourse-synthesis satellite for gather.

Turns a corpus of comments and threads into a weighted, clustered, re-checkable
reading of the discourse. Sentiment is a weight and a signal here, never an
accept gate. Stdlib only; deterministic; every digest carries a receipt.
"""
from chorus.item import DiscourseItem, normalize

__version__ = "0.1.0"
__all__ = ["DiscourseItem", "normalize"]
