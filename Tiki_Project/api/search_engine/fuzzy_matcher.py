# ============================================================
# FUZZY MATCHER — Typo-tolerant token matching
#
# Uses rapidfuzz if available, falls back to difflib.
# Designed for short Vietnamese product tokens.
# ============================================================

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import rapidfuzz (faster), fall back to difflib
try:
    from rapidfuzz import fuzz as _fuzz
    from rapidfuzz import process as _process
    _HAS_RAPIDFUZZ = True
    logger.debug("FuzzyMatcher: using rapidfuzz.")
except ImportError:
    import difflib as _difflib
    _HAS_RAPIDFUZZ = False
    logger.debug("FuzzyMatcher: rapidfuzz not found, using difflib.")


def token_similarity(a: str, b: str) -> float:
    """
    Return similarity [0.0, 1.0] between two normalized tokens.
    Uses partial_ratio to handle substring matches well.
    """
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if _HAS_RAPIDFUZZ:
        return _fuzz.token_sort_ratio(a, b) / 100.0
    else:
        return _difflib.SequenceMatcher(None, a, b).ratio()


def best_match_score(query_tokens: list[str], doc_tokens: list[str]) -> float:
    """
    For each query token, find the best-matching doc token.
    Returns average best-match score across all query tokens.

    This handles typos like "điên thoại" → "dien thoai".
    """
    if not query_tokens or not doc_tokens:
        return 0.0

    total = 0.0
    for qt in query_tokens:
        if not qt:
            continue
        best = 0.0
        for dt in doc_tokens:
            s = token_similarity(qt, dt)
            if s > best:
                best = s
                if best >= 1.0:
                    break
        total += best

    return total / len(query_tokens)


def query_fuzzy_score(
    query_tokens: list[str],
    doc_text: str,
    threshold: float = 0.75,
) -> float:
    """
    Compute fuzzy match score between a query and a document.

    Args:
        query_tokens: Normalized tokens from the query.
        doc_text:     Full normalized document text.
        threshold:    Minimum similarity to count a token as matched.

    Returns:
        Score in [0.0, 1.0].
    """
    if not query_tokens or not doc_text:
        return 0.0

    doc_tokens = doc_text.split()
    if not doc_tokens:
        return 0.0

    matched = 0
    for qt in query_tokens:
        for dt in doc_tokens:
            if token_similarity(qt, dt) >= threshold:
                matched += 1
                break

    return matched / len(query_tokens)
