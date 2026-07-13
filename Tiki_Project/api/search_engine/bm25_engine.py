# ============================================================
# BM25 ENGINE — Lightweight BM25 + TF-IDF scoring
#
# Uses rank_bm25 if available, falls back to a pure-Python
# BM25Okapi implementation so there are no hard dependencies.
#
# Index is built at startup over all product search-documents.
# ============================================================

import math
import logging
from collections import Counter
from typing import Any

from .normalizer import tokenize

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Pure-Python BM25 Okapi (fallback when rank_bm25 not installed)
# ------------------------------------------------------------------
class _BM25Okapi:
    """Minimal BM25 Okapi implementation (no external deps)."""

    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.avgdl = sum(len(doc) for doc in corpus) / max(self.corpus_size, 1)

        # Document frequencies
        df: dict[str, int] = {}
        self.tf_cache: list[dict[str, float]] = []
        for doc in corpus:
            freq = Counter(doc)
            self.tf_cache.append(dict(freq))
            for term in freq:
                df[term] = df.get(term, 0) + 1

        # IDF (smoothed BM25 variant)
        self.idf: dict[str, float] = {}
        for term, freq in df.items():
            self.idf[term] = math.log(
                (self.corpus_size - freq + 0.5) / (freq + 0.5) + 1
            )

    def get_scores(self, query_tokens: list[str]) -> list[float]:
        scores = [0.0] * self.corpus_size
        for i, tf_map in enumerate(self.tf_cache):
            dl = sum(tf_map.values())
            for term in query_tokens:
                if term not in tf_map:
                    continue
                tf = tf_map[term]
                idf = self.idf.get(term, 0.0)
                numer = tf * (self.k1 + 1)
                denom = tf + self.k1 * (1 - self.b + self.b * dl / max(self.avgdl, 1))
                scores[i] += idf * numer / max(denom, 1e-9)
        return scores


# ------------------------------------------------------------------
# BM25Index — public API
# ------------------------------------------------------------------
class BM25Index:
    """
    Wraps rank_bm25 (preferred) or the built-in fallback.
    Build once at startup, query at runtime.
    """

    def __init__(self, documents: list[str]):
        """
        Args:
            documents: List of pre-built search documents (one per product).
                       Each document is a normalized, space-separated string.
        """
        self._tokenized_corpus: list[list[str]] = [tokenize(doc) for doc in documents]
        self._bm25 = self._init_bm25()
        logger.info(f"BM25Index: indexed {len(documents)} documents.")

    def _init_bm25(self) -> Any:
        try:
            from rank_bm25 import BM25Okapi  # type: ignore
            bm25 = BM25Okapi(self._tokenized_corpus)
            logger.info("BM25Index: using rank_bm25 library.")
            return bm25
        except ImportError:
            logger.info("BM25Index: rank_bm25 not found, using built-in implementation.")
            return _BM25Okapi(self._tokenized_corpus)

    def get_scores(self, query_tokens: list[str]) -> list[float]:
        """Return BM25 scores for all documents given query tokens."""
        if not query_tokens:
            return [0.0] * len(self._tokenized_corpus)
        raw = self._bm25.get_scores(query_tokens)
        # rank_bm25 returns numpy array; convert to plain Python list
        raw = [float(x) for x in raw]
        # Normalize to [0, 1] range
        max_score = max(raw) if raw else 1.0
        if max_score <= 0:
            return [0.0] * len(raw)
        return [s / max_score for s in raw]
