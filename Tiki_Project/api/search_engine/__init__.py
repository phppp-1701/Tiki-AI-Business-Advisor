# ============================================================
# SEARCH ENGINE PACKAGE
# Lightweight, modular search engine for Tiki products.
# Components:
#   - normalizer.py       : Vietnamese text normalization + alias mapping
#   - synonym_map.py      : Compound phrase detection + synonym expansion
#   - bm25_engine.py      : BM25 + TF-IDF scoring
#   - fuzzy_matcher.py    : Typo-tolerant token matching
#   - category_matcher.py : Semantic category detection from real data
#   - smart_search.py     : Main search coordinator (v3)
# ============================================================
from .smart_search import SmartSearch
from .category_matcher import CategoryMatcher

__all__ = ["SmartSearch", "CategoryMatcher"]
