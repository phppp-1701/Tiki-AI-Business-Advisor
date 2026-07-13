# ============================================================
# SMART SEARCH v3 — Category-Aware, Fault-Tolerant Search Engine
#
# Search flow:
#   1. Normalize + alias-map query (joined words, typos, synonyms)
#   2. Category matching via CategoryMatcher (semantic BM25 + compact fuzzy)
#      → category_locked    (confidence >= 0.68): results ONLY from matched category
#      → category_preferred (confidence >= 0.35): matched category boosted, others allowed
#      → full_scan          (confidence < 0.35) : search all products
#   3. Within matched scope: rank by structured score
#        exact_name_score + category_score + phrase_score + fuzzy_score + semantic_score + popularity_bonus
#   4. Fallback: fuzzy → popular (only if very few results)
#   5. Products outside locked category NEVER appear in primary results
#      (they may appear in related_suggestions)
# ============================================================

import logging
import math
import re
from typing import Any, Optional

from .normalizer import normalize, tokenize, build_search_doc, preprocess_query, has_diacritics, accent_lower
from .synonym_map import detect_compound, expand_query_simple, detect_context_query
from .bm25_engine import BM25Index
from .fuzzy_matcher import query_fuzzy_score, token_similarity
from .category_matcher import CategoryMatcher, THRESHOLD_HIGH, THRESHOLD_MED

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Score weights — components of final_score
# ------------------------------------------------------------------
W_EXACT_PHRASE    = 0.90   # Exact normalized phrase in name
W_ALL_TOKENS_NAME = 0.72   # All meaningful query tokens in name
W_SINGLE_TOKEN    = 0.61   # Single meaningful token in name
W_CATEGORY_BONUS  = 0.15   # In-scope category bonus (when category_preferred/locked)
W_PHRASE_SYN      = 0.55   # Synonym/phrase alias found in name
W_BM25_MAX        = 0.28   # Max BM25 contribution
W_FUZZY_MAX       = 0.40   # Max fuzzy fallback contribution
W_POPULARITY_MAX  = 0.10   # Max popularity bonus (auxiliary only)

# Thresholds
GOOD_RESULT_THRESHOLD = 0.20   # Score above this → "relevant result"
MIN_GOOD_RESULTS      = 3      # Need at least this many relevant results
FALLBACK_THRESHOLD    = 5      # Total results < this → add popular fallback
FUZZY_THRESHOLD       = 0.80   # Token-level fuzzy match threshold
MIN_SYNONYM_LEN       = 4      # Min chars for synonym phrase to count

# Vietnamese stopwords — excluded from meaningful-token checks
_VI_STOPWORDS = {
    "cho", "va", "cua", "de", "thi", "la", "co", "voi",
    "trong", "ngoai", "tren", "duoi", "hay", "hoac",
    "tu", "den", "khong", "mot", "cac", "nhung",
    "rat", "kha", "that", "hon", "nhat", "da", "dang",
    "cung", "nen", "ma", "neu",
}


def _word_in_text(word: str, text: str) -> bool:
    return bool(re.search(r'\b' + re.escape(word) + r'\b', text))


def _token_set(text: str) -> set[str]:
    return set(text.split())


def _get_min_window_and_order(query_tokens: list[str], name_tokens_list: list[str]) -> tuple[float, bool]:
    # Find all indices of each query token in name_tokens_list
    token_indices = {}
    for qt in query_tokens:
        indices = [i for i, t in enumerate(name_tokens_list) if t == qt]
        if not indices:
            return float('inf'), False
        token_indices[qt] = indices

    import itertools
    best_window = float('inf')
    correct_order = False

    keys = list(token_indices.keys())
    idx_lists = [token_indices[k] for k in keys]
    
    for combo in itertools.product(*idx_lists):
        min_i = min(combo)
        max_i = max(combo)
        window_size = max_i - min_i + 1
        
        ordered_indices = [combo[keys.index(qt)] for qt in query_tokens]
        is_ordered = all(ordered_indices[i] < ordered_indices[i+1] for i in range(len(ordered_indices)-1))
        
        if window_size < best_window:
            best_window = window_size
            correct_order = is_ordered
        elif window_size == best_window and is_ordered:
            correct_order = True

    return best_window, correct_order


class SmartSearch:
    """
    Category-aware, fault-tolerant search engine for Tiki products.

    Search modes:
      category_locked    → only products in matched_category appear in results
      category_preferred → matched_category boosted; others allowed if score very high
      full_scan          → all products scored, no category restriction
    """

    def __init__(self, products_df: Any, resolve_url_fn=None, slug_to_display: dict | None = None):
        self._df = products_df
        self._resolve_url = resolve_url_fn
        # Map raw category slugs → display names for API response
        self._slug_to_display: dict[str, str] = slug_to_display or {}
        self._index: Optional[BM25Index] = None
        self._docs: list[str] = []
        self._name_norms: list[str] = []
        self._cat_slugs: list[str] = []         # raw category slug from data
        self._cat_norms: list[str] = []         # normalized category (no-accent, no-dash)
        self._popularity_norm: list[float] = []
        self._category_matcher: Optional[CategoryMatcher] = None

        if products_df is not None and not products_df.empty:
            self._build_index()

    # ------------------------------------------------------------------
    # Index building
    # ------------------------------------------------------------------
    def _build_index(self) -> None:
        logger.info("SmartSearch v3: building index...")
        df = self._df

        max_qty = float(df["quantity_sold"].max()) if "quantity_sold" in df.columns else 1.0
        max_qty = max(max_qty, 1.0)

        self._docs = []
        self._name_norms = []
        self._name_originals = []  # lowercase-preserving-accent for accent-aware matching
        self._cat_slugs = []
        self._cat_norms = []
        self._popularity_norm = []

        for _, row in df.iterrows():
            name     = str(row.get("name", ""))
            category = str(row.get("category", ""))
            brand    = str(row.get("brand_name", row.get("brand", row.get("seller_name", ""))))
            desc     = str(row.get("description", row.get("short_description", "")))

            name_n = normalize(name)
            # Normalize category: replace hyphens and spaces, strip accents
            cat_n  = normalize(category.replace("-", " "))
            doc    = build_search_doc(name, category, brand, desc)

            self._name_norms.append(name_n)
            self._name_originals.append(accent_lower(name))  # preserve diacritics
            self._cat_slugs.append(category)     # keep raw slug
            self._cat_norms.append(cat_n)        # normalized for matching
            self._docs.append(doc)

            qty = float(row.get("quantity_sold", 0))
            self._popularity_norm.append(math.log1p(qty) / math.log1p(max_qty))

        self._index = BM25Index(self._docs)

        # Build category matcher from the same dataframe
        self._category_matcher = CategoryMatcher(df)

        logger.info(f"SmartSearch v3: index ready ({len(self._docs)} products).")

    # ------------------------------------------------------------------
    # Public search entry point
    # ------------------------------------------------------------------
    def search(
        self,
        keyword: str,
        limit: int = 20,
        debug: bool = False,
    ) -> list[dict]:
        """
        Search products by keyword.

        Returns list of product dicts. Each product may have '_debug' key if debug=True.
        Products in results are guaranteed to be from the matched_category when
        result_type == 'category_locked'.
        """
        if self._index is None or self._df is None or self._df.empty:
            return []

        # ── Step 1: Query preprocessing ───────────────────────────────
        raw_query      = keyword.strip()
        # Detect if user typed with Vietnamese diacritics.
        # If yes: use accent-preserving match on product original names.
        # If no:  normalize freely (bỏ dấu) as before.
        query_has_accent = has_diacritics(raw_query)
        # Original lowercased query (accent preserved) for accent-aware matching
        query_original   = accent_lower(raw_query)
        # Tokens of original query (with accent) for token-level accent-aware match
        query_orig_tokens = set(query_original.split()) if query_has_accent else set()

        query_norm    = preprocess_query(raw_query)        # alias-mapped, no-accent
        query_tokens  = [t for t in query_norm.split() if t]
        query_compact = query_norm.replace(" ", "")       # for joined-word matching

        if not query_tokens:
            return []

        # ── Step 2: Category matching ─────────────────────────────────
        cat_match = self._category_matcher.match(
            query_norm=query_norm,
            query_compact=query_compact,
        ) if self._category_matcher else {
            "matched_category": None, "confidence": 0.0,
            "result_type": "full_scan", "all_scores": {}
        }

        matched_category: str | None = cat_match["matched_category"]
        cat_confidence: float        = cat_match["confidence"]
        result_type: str             = cat_match["result_type"]

        # ── Step 3: Compound phrase detection ─────────────────────────
        compound       = detect_compound(query_norm)
        is_compound    = compound is not None
        phrase_synonyms: list[str] = compound.get("synonyms", []) if is_compound else []

        # ── Step 4: Context query detection ("A cho B") ───────────────
        context_query = detect_context_query(query_norm)

        # ── Step 5: BM25 tokens ───────────────────────────────────────
        if is_compound:
            bm25_tokens = list(query_tokens)
            seen: set[str] = set(bm25_tokens)
            for syn in phrase_synonyms:
                for sub in syn.split():
                    if sub not in seen:
                        seen.add(sub)
                        bm25_tokens.append(sub)
        else:
            expanded    = expand_query_simple(query_tokens)
            bm25_tokens = []
            seen_b: set[str] = set()
            for t in expanded:
                for sub in t.split():
                    if sub not in seen_b:
                        seen_b.add(sub)
                        bm25_tokens.append(sub)

        bm25_scores = self._index.get_scores(bm25_tokens)
        bm25_max    = max(bm25_scores) if any(s > 0 for s in bm25_scores) else 1.0

        # ── Step 6: Determine search scope ────────────────────────────
        # matched_cat_norm: normalized form of slug (e.g. "dien thoai may tinh bang")
        matched_cat_norm = (
            self._category_matcher.get_category_norm(matched_category)
            if matched_category and self._category_matcher else ""
        )

        # ── Step 7: Score each product ────────────────────────────────
        n = len(self._docs)
        query_token_set   = set(query_tokens)
        meaningful_tokens = query_token_set - _VI_STOPWORDS

        primary_results: list[tuple[int, float, dict]]  = []
        related_results: list[tuple[int, float, dict]]  = []

        for i in range(n):
            name_n       = self._name_norms[i]
            name_orig    = self._name_originals[i]   # lowercased, accent preserved
            cat_n        = self._cat_norms[i]     # normalized slug for this product
            cat_slug     = self._cat_slugs[i]     # raw slug
            bm25         = bm25_scores[i]
            pop          = self._popularity_norm[i]
            name_toks    = _token_set(name_n)
            # Token set of original accented name (for accent-aware matching)
            name_orig_toks = set(name_orig.split())

            # ── Is this product in matched category? ───────────────
            in_matched_cat = (
                matched_category is not None
                and cat_slug == matched_category
            )

            # ── category_locked: skip products outside matched category ──
            if result_type == "category_locked" and matched_category and not in_matched_cat:
                # Don't include in primary results; might add as related later
                related_results.append((i, 0.0, {"matched_reason": "outside_locked_category"}))
                continue

            # ── Component scores ───────────────────────────────────
            exact_name_score = 0.0
            category_score   = 0.0
            phrase_score     = 0.0
            fuzzy_score      = 0.0
            semantic_score   = 0.0
            match_reasons: list[str] = []

            # exact_name_score
            # ─────────────────────────────────────────────────────────────
            # ACCENT-AWARE EXACT MATCHING:
            # If user typed with diacritics (e.g. "váy"), we match against
            # the original lowercased product name (accent preserved) so
            # "váy" only matches products with "váy" in name, NOT "vảy".
            # If user typed without diacritics (e.g. "vay"), we fall through
            # to the normalized (no-accent) match as before.
            # ─────────────────────────────────────────────────────────────
            if query_has_accent:
                # Check on ORIGINAL accented name
                if query_original and _word_in_text(query_original, name_orig):
                    exact_name_score = W_EXACT_PHRASE
                    match_reasons.append("exact_phrase_in_name")
                elif (
                    query_orig_tokens
                    and len(query_orig_tokens - _VI_STOPWORDS) >= max(1, len(query_orig_tokens) // 2)
                    and (query_orig_tokens - _VI_STOPWORDS).issubset(name_orig_toks)
                    and len(query_orig_tokens - _VI_STOPWORDS) >= 2
                ):
                    # Verify window size and order for multi-word accented matching
                    name_orig_list = name_orig.split()
                    window, ordered = _get_min_window_and_order(list(query_orig_tokens - _VI_STOPWORDS), name_orig_list)
                    if window <= len(query_orig_tokens - _VI_STOPWORDS) + 2 and ordered:
                        exact_name_score = W_ALL_TOKENS_NAME
                        match_reasons.append("all_tokens_in_name")
                elif (
                    query_orig_tokens
                    and len(query_orig_tokens - _VI_STOPWORDS) == 1
                    and (query_orig_tokens - _VI_STOPWORDS).issubset(name_orig_toks)
                ):
                    exact_name_score = W_SINGLE_TOKEN
                    match_reasons.append("single_token_in_name")
            else:
                # No-accent query: normalize-based matching (original behavior)
                if query_norm and _word_in_text(query_norm, name_n):
                    exact_name_score = W_EXACT_PHRASE
                    match_reasons.append("exact_phrase_in_name")
                elif (
                    meaningful_tokens
                    and len(meaningful_tokens) >= max(1, len(query_token_set) // 2)
                    and meaningful_tokens.issubset(name_toks)
                    and len(meaningful_tokens) >= 2
                ):
                    # Verify window size and order for multi-word no-accent matching
                    name_n_list = name_n.split()
                    window, ordered = _get_min_window_and_order(list(meaningful_tokens), name_n_list)
                    if window <= len(meaningful_tokens) + 2 and ordered:
                        exact_name_score = W_ALL_TOKENS_NAME
                        match_reasons.append("all_tokens_in_name")
                elif len(meaningful_tokens) == 1 and meaningful_tokens.issubset(name_toks):
                    exact_name_score = W_SINGLE_TOKEN
                    match_reasons.append("single_token_in_name")

            # category_score
            if result_type in ("category_locked", "category_preferred") and in_matched_cat:
                category_score = W_CATEGORY_BONUS
                match_reasons.append("in_matched_category")
            elif result_type == "full_scan":
                # Generic token overlap with category
                q_in_cat = len(query_token_set & _token_set(cat_n))
                if q_in_cat > 0:
                    category_score = min(0.07, q_in_cat * 0.035)
                    match_reasons.append("category_token_overlap")

            # phrase_score (synonym in name)
            if phrase_synonyms and not exact_name_score:
                matched_syn = [
                    syn for syn in phrase_synonyms
                    if len(syn) >= MIN_SYNONYM_LEN and _word_in_text(syn, name_n)
                ]
                if matched_syn:
                    phrase_score = W_PHRASE_SYN
                    match_reasons.append(f"synonym_in_name:{matched_syn[0]}")

            # semantic_score (BM25)
            if bm25 > 0:
                semantic_score = (bm25 / bm25_max) * W_BM25_MAX
                if not match_reasons:
                    match_reasons.append("bm25_token_match")

            # Skip products with no signal
            has_signal = (
                exact_name_score > 0
                or phrase_score > 0
                or semantic_score > 0.05
                or (result_type == "category_locked" and in_matched_cat)
            )
            if not has_signal:
                continue

            # popularity bonus (auxiliary only)
            pop_bonus = pop * W_POPULARITY_MAX

            final = min(1.0,
                exact_name_score + category_score + phrase_score
                + fuzzy_score + semantic_score + pop_bonus
            )

            # category_preferred: demote out-of-scope products significantly,
            # UNLESS they have a strong name match (handles data quality issues
            # where product category slug is wrong in the dataset)
            if result_type == "category_preferred" and not in_matched_cat:
                # Allow through: exact_phrase (0.90), all_tokens (0.72), single_token (0.61)
                if exact_name_score < W_SINGLE_TOKEN:
                    final = min(final, 0.16)   # cap weak semantic-only matches
                    match_reasons.append("out_of_preferred_category")

            dbg = {
                "final_score":        round(final, 4),
                "exact_name_score":   round(exact_name_score, 4),
                "category_score":     round(category_score, 4),
                "phrase_score":       round(phrase_score, 4),
                "fuzzy_score":        round(fuzzy_score, 4),
                "semantic_score":     round(semantic_score, 4),
                "popularity_score":   round(pop_bonus, 4),
                "matched_reason":     " | ".join(match_reasons) if match_reasons else "weak_signal",
                "in_matched_cat":     in_matched_cat,
                "result_type":        result_type,
                "matched_category":   matched_category,
                "category_confidence": round(cat_confidence, 4),
            }
            primary_results.append((i, final, dbg))

        # Sort primary results
        primary_results.sort(key=lambda x: x[1], reverse=True)

        # ── Step 8: Context query handling ("A cho B") ─────────────
        context_label: str | None = None
        if context_query:
            primary_results, context_label = self._apply_context_filter(
                context_query, primary_results
            )

        # ── Step 9: Fuzzy fallback if needed ──────────────────────
        good = [t for t in primary_results if t[1] >= GOOD_RESULT_THRESHOLD]

        if len(good) < MIN_GOOD_RESULTS:
            scope_indices: set[int] | None = None
            if result_type == "category_locked" and matched_category:
                scope_indices = {
                    i for i in range(n)
                    if self._cat_slugs[i] == matched_category
                }
            fuzzy_adds = self._fuzzy_fallback(
                query_tokens, bm25_scores,
                already_found={i for i, _, _ in good},
                limit=min(limit, 10),
                scope_indices=scope_indices,
            )
            good = sorted(good + fuzzy_adds, key=lambda x: x[1], reverse=True)
            primary_results = good + [
                t for t in primary_results
                if t[0] not in {x[0] for x in good}
            ]

        # ── Step 10: Popular fallback (last resort) ────────────────
        if len(primary_results) < FALLBACK_THRESHOLD:
            scope_indices_fb: set[int] | None = None
            if result_type == "category_locked" and matched_category:
                scope_indices_fb = {
                    i for i in range(n)
                    if self._cat_slugs[i] == matched_category
                }
            pop_fb = self._popular_fallback(
                already_found={i for i, _, _ in primary_results},
                limit=min(limit, 5),
                scope_indices=scope_indices_fb,
            )
            primary_results = sorted(primary_results + pop_fb, key=lambda x: x[1], reverse=True)

        # ── Step 11: Build output ──────────────────────────────────
        results: list[dict] = []
        seen_ids: set[str] = set()

        # Threshold to cut off long-tail noise (out-of-scope weak matches are capped at 0.16)
        MIN_ACCEPTABLE_SCORE = 0.17

        for i, score, dbg in primary_results[:limit]:
            # Stop returning garbage if we already have enough decent results
            if score < MIN_ACCEPTABLE_SCORE and len(results) >= MIN_GOOD_RESULTS:
                break

            row = self._df.iloc[i]
            pid = str(row.get("product_id", ""))
            if pid in seen_ids:
                continue
            seen_ids.add(pid)

            url = ""
            if self._resolve_url:
                url = self._resolve_url(
                    product_id=row.get("product_id"),
                    name=row.get("name"),
                    category=row.get("category"),
                )

            cat_display = self._slug_to_display.get(
                str(row.get("category", "")),
                str(row.get("category", ""))
            )
            product: dict = {
                "product_id":        pid,
                "title":             str(row.get("name", "")),
                "categoryName":      cat_display,
                "price":             float(row.get("original_price", 0)),
                "rating":            float(row.get("original_rating", 0)),
                "boughtInLastMonth": int(row.get("quantity_sold", 0)),
                "estimated_revenue": float(row.get("original_price", 0)) * float(row.get("quantity_sold", 0)),
                "product_url":       url,
                "url_path":          url,
            }
            
            # Add hierarchical categories for context detection
            import pandas as pd
            deepest_cat = product["categoryName"]
            for lvl in range(1, 13):
                cat_key = f"category_level_{lvl}"
                cat_val = row.get(cat_key)
                if pd.notna(cat_val) and str(cat_val).strip() and str(cat_val).lower() != "nan":
                    val = str(cat_val).strip()
                    product[cat_key] = val
                    deepest_cat = val
                    
            product["categoryName"] = deepest_cat
            if debug:
                product["_debug"] = {
                    **dbg,
                    "raw_query":          raw_query,
                    "normalized_query":   query_norm,
                    "matched_category":   matched_category,
                    "category_confidence": round(cat_confidence, 4),
                    "result_type":        result_type,
                }
            if context_label and "fallback_context_miss" in dbg.get("matched_reason", ""):
                product["_fallback_label"] = context_label

            results.append(product)

        # ── Step 12: Final Context Query Enforcement ────────────────
        if context_query:
            main = context_query["main_product"]
            main_tokens = set(main.split())
            valid_results = []
            for r in results:
                name_n = normalize(r.get("title", ""))
                cat_n = normalize(str(r.get("categoryName", "")).lower())
                name_toks = set(name_n.split())
                if bool(main_tokens & name_toks) or _word_in_text(main, name_n) or _word_in_text(main, cat_n):
                    valid_results.append(r)
            results = valid_results

        logger.debug(
            f"SmartSearch v3: '{keyword}' → '{query_norm}' "
            f"cat={matched_category}({cat_confidence:.2f}) "
            f"type={result_type} results={len(results)}"
        )
        return results

    # ------------------------------------------------------------------
    # Context query filter ("A cho B")
    # ------------------------------------------------------------------
    def _apply_context_filter(
        self,
        context_query: dict,
        scored: list[tuple[int, float, dict]],
    ) -> tuple[list[tuple[int, float, dict]], str | None]:
        main = context_query["main_product"]
        ctx  = context_query["context_term"]
        main_tokens = set(main.split())
        ctx_tokens  = set(ctx.split()) - _VI_STOPWORDS

        boosted = []
        for i, score, dinfo in scored:
            name_n = self._name_norms[i]
            cat_n = self._cat_slugs[i].replace("-", " ")
            name_toks = _token_set(name_n)
            
            # Check main in both name and category
            has_main = bool(main_tokens & name_toks) or _word_in_text(main, name_n) or _word_in_text(main, cat_n)
            has_ctx  = bool(ctx_tokens & name_toks) or _word_in_text(ctx, name_n) or _word_in_text(ctx, cat_n)

            if not has_main:
                # If the main item (e.g. "váy" in "váy cho nam") is entirely missing,
                # drop it completely to prevent returning irrelevant items like "dép nam".
                continue

            if has_ctx:
                new_score = min(1.0, score + 0.18)
                dinfo = dict(dinfo, matched_reason=dinfo["matched_reason"] + "|context_both_match",
                             final_score=round(new_score, 4))
                boosted.append((i, new_score, dinfo))
            else:
                boosted.append((i, score, dinfo))

        boosted.sort(key=lambda x: x[1], reverse=True)
        both_count = sum(
            1 for _, s, d in boosted
            if "context_both_match" in d.get("matched_reason", "") and s >= GOOD_RESULT_THRESHOLD
        )

        if both_count < 2:
            label = f"Gợi ý: '{main}' có thể không liên quan '{ctx}' — kết quả gần nhất"
            final = []
            for i, score, dinfo in boosted:
                if "context_both_match" not in dinfo.get("matched_reason", ""):
                    dinfo = dict(dinfo, matched_reason="fallback_context_miss|" + dinfo["matched_reason"])
                final.append((i, score, dinfo))
            return final, label

        return boosted, None

    # ------------------------------------------------------------------
    # Fuzzy fallback
    # ------------------------------------------------------------------
    def _fuzzy_fallback(
        self,
        query_tokens: list[str],
        bm25_scores: list[float],
        already_found: set[int],
        limit: int,
        scope_indices: set[int] | None = None,
    ) -> list[tuple[int, float, dict]]:
        n = len(self._docs)
        sorted_by_bm25 = sorted(range(n), key=lambda i: bm25_scores[i], reverse=True)
        candidates = [
            i for i in sorted_by_bm25[:300]
            if i not in already_found
            and (scope_indices is None or i in scope_indices)
        ]
        results = []
        for i in candidates:
            fuzz = query_fuzzy_score(query_tokens, self._docs[i], threshold=FUZZY_THRESHOLD)
            if fuzz >= 0.50:
                pop = self._popularity_norm[i]
                fscore = fuzz * W_FUZZY_MAX + pop * W_POPULARITY_MAX
                results.append((i, fscore, {
                    "final_score":      round(fscore, 4),
                    "exact_name_score": 0.0,
                    "category_score":   0.0,
                    "phrase_score":     0.0,
                    "fuzzy_score":      round(fuzz * W_FUZZY_MAX, 4),
                    "semantic_score":   round(bm25_scores[i] * W_BM25_MAX, 4),
                    "popularity_score": round(pop * W_POPULARITY_MAX, 4),
                    "matched_reason":   f"fuzzy_typo|fuzz={fuzz:.2f}",
                    "in_matched_cat":   scope_indices is not None and i in (scope_indices or set()),
                }))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    # ------------------------------------------------------------------
    # Popular fallback
    # ------------------------------------------------------------------
    def _popular_fallback(
        self,
        already_found: set[int],
        limit: int,
        scope_indices: set[int] | None = None,
    ) -> list[tuple[int, float, dict]]:
        candidates = [
            (i, pop)
            for i, pop in enumerate(self._popularity_norm)
            if i not in already_found
            and (scope_indices is None or i in scope_indices)
        ]
        candidates.sort(key=lambda x: x[1], reverse=True)
        results = []
        for i, pop in candidates[:limit]:
            score = pop * 0.05
            results.append((i, score, {
                "final_score":      round(score, 4),
                "exact_name_score": 0.0,
                "category_score":   0.0,
                "phrase_score":     0.0,
                "fuzzy_score":      0.0,
                "semantic_score":   0.0,
                "popularity_score": round(pop * W_POPULARITY_MAX, 4),
                "matched_reason":   "popular_fallback",
                "in_matched_cat":   scope_indices is not None and i in (scope_indices or set()),
            }))
        return results
