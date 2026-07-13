# ============================================================
# CATEGORY MATCHER — Semantic category detection from query
#
# How it works:
#   1. At build time: reads real categories from products_df.
#      For each category, creates a "category document" containing:
#        - slug tokens (dien thoai may tinh bang)
#        - compact form (dienthoamaytinhbang)
#        - top-N frequent tokens from product names in that category
#        - top brands in that category
#        - synonym seed terms (declared per category, not hardcoded per query)
#        - BM25 index over all category documents
#
#   2. At query time:
#      - Normalize + alias-map query → canonical form
#      - Also create compact form of query for joined-word matching
#      - Score query against all category documents via BM25 + fuzzy compact overlap
#      - If best score >= THRESHOLD_HIGH (0.70): category_locked
#      - If best score >= THRESHOLD_MED  (0.40): category_preferred
#      - Otherwise: full_scan (search everything)
#
# Design principles:
#   - No if/else hardcoded per query
#   - All logic is data-driven from products_df
#   - Synonym seeds only describe the category concept, not force results
#   - compact fuzzy matching handles dienthoai / tainghe / truyentranh etc.
# ============================================================

import math
import logging
import re
from collections import Counter
from typing import Optional

from .normalizer import normalize
from .fuzzy_matcher import token_similarity

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Confidence thresholds
# ------------------------------------------------------------------
THRESHOLD_HIGH = 0.65   # category_locked: only search within this category
THRESHOLD_MED  = 0.33   # category_preferred: boost this category strongly

# Min score for compact-form fuzzy match to trigger category mapping
COMPACT_FUZZY_MIN = 0.82

# How many top tokens/brands to include from each category
TOP_TOKENS_PER_CATEGORY = 30
TOP_BRANDS_PER_CATEGORY = 10

# ------------------------------------------------------------------
# Per-category synonym seeds (small, concept-level — NOT per-query)
# These are seeds describing what the category IS, not forcing results.
# Only add terms that are clearly synonymous with the category concept.
# ------------------------------------------------------------------
_CATEGORY_SYNONYM_SEEDS: dict[str, list[str]] = {
    "dien-thoai-may-tinh-bang": [
        "smartphone", "phone", "mobile", "dien thoai", "may tinh bang",
        "tablet", "ipad", "android", "iphone",
    ],
    "thiet-bi-dien-tu": [
        "laptop", "may tinh xach tay", "notebook", "tivi", "man hinh",
        "loa", "camera", "may anh", "may giat",
    ],
    "do-gia-dung": [
        "noi com dien", "may loc nuoc", "binh giu nhiet", "hop dung do",
        "dung cu bep", "may rua bat",
    ],
    "my-pham-lam-dep": [
        "son moi", "sua rua mat", "kem chong nang", "kem duong am",
        "mat na", "nuoc hoa", "serum", "toner", "cleanser", "lipstick",
        "skincare", "beauty", "cosmetic",
    ],
    "sach-truyen": [
        "sach", "truyen", "truyen tranh", "manga", "comic", "book",
        "novel", "tap chi",
    ],
    "the-thao-da-ngoai": [
        "giay the thao", "ao the thao", "do the thao", "bong da",
        "running", "gym", "fitness", "sport", "sneaker",
    ],
    "thoi-trang-nam": [
        "ao thun nam", "ao phong nam", "quan jean nam", "ao khoac nam",
        "quan nam", "do nam", "thoi trang nam",
    ],
    "thoi-trang-nu": [
        "ao thun nu", "vay", "chan vay", "dam nu", "ao nu", "do nu",
        "thoi trang nu", "skirt", "dress", "dam", "vay dam", "ao dam",
        "bikini", "bra",
    ],
    "o-to-xe-may": [
        "xe may", "o to", "xe hoi", "xe dap", "phu kien xe",
        "dau nhot", "lop xe",
    ],
}


class CategoryMatcher:
    """
    Semantic category detector.
    Matches a search query against all real categories in the dataset
    using BM25 scoring over category documents + compact fuzzy matching.
    """

    def __init__(self, products_df):
        self._cat_docs: dict[str, str]   = {}   # slug → full category document string
        self._cat_norms: dict[str, str]  = {}   # slug → normalized slug (dashes removed)
        self._cat_compact: dict[str, str] = {}  # slug → compact (no spaces, for fuzzy)
        self._cat_tokens: dict[str, list[str]] = {}  # slug → token list for BM25
        self._slug_list: list[str] = []          # ordered list of slugs

        if products_df is not None and not products_df.empty:
            self._build(products_df)

    # ------------------------------------------------------------------
    # Build category index
    # ------------------------------------------------------------------
    def _build(self, df) -> None:
        logger.info("CategoryMatcher: building category index...")

        # Group products by category slug
        cat_groups: dict[str, list] = {}
        for _, row in df.iterrows():
            slug = str(row.get("category", "")).strip()
            if slug:
                cat_groups.setdefault(slug, []).append(row)

        for slug, rows in cat_groups.items():
            # 1. Slug tokens (replace hyphens with spaces, normalize)
            slug_norm = normalize(slug.replace("-", " "))
            slug_compact = slug_norm.replace(" ", "")

            # 2. Top tokens from product names in this category
            name_token_counter: Counter = Counter()
            brand_counter: Counter = Counter()
            for row in rows:
                name = str(row.get("name", ""))
                brand = str(row.get("brand_name", row.get("brand", "")))
                name_norm = normalize(name)
                for tok in name_norm.split():
                    if len(tok) >= 3 and tok.isalpha():
                        name_token_counter[tok] += 1
                if brand and brand.lower() not in ("no brand", "nan", "none", ""):
                    brand_counter[normalize(brand)] += 1

            top_name_tokens = [t for t, _ in name_token_counter.most_common(TOP_TOKENS_PER_CATEGORY)]
            top_brands = [b for b, _ in brand_counter.most_common(TOP_BRANDS_PER_CATEGORY)]

            # 3. Synonym seeds for this category
            seeds = [normalize(s) for s in _CATEGORY_SYNONYM_SEEDS.get(slug, [])]

            # 4. Build weighted category document
            # slug tokens × 4 (highest weight for exact slug match)
            parts = [slug_norm] * 4
            # synonym seeds × 3
            for seed in seeds:
                parts.extend([seed] * 3)
            # brands × 2
            for brand in top_brands:
                parts.extend([brand] * 2)
            # top name tokens × 1
            parts.extend(top_name_tokens)

            doc = " ".join(parts)

            self._cat_docs[slug] = doc
            self._cat_norms[slug] = slug_norm
            self._cat_compact[slug] = slug_compact
            self._cat_tokens[slug] = doc.split()
            self._slug_list.append(slug)

        logger.info(f"CategoryMatcher: indexed {len(self._slug_list)} categories: {self._slug_list}")

    # ------------------------------------------------------------------
    # Score query against all categories
    # ------------------------------------------------------------------
    def match(self, query_norm: str, query_compact: str = "") -> dict:
        """
        Score a normalized query against all category documents.

        Args:
            query_norm:    Normalized query string (space-separated tokens)
            query_compact: Compact form of query (no spaces) for joined-word matching

        Returns:
            {
                "matched_category": str | None,
                "confidence": float,
                "result_type": "category_locked" | "category_preferred" | "full_scan",
                "all_scores": {slug: float},
            }
        """
        if not query_norm or not self._slug_list:
            return _null_match()

        query_tokens = [t for t in query_norm.split() if t]
        query_compact_form = query_compact or query_norm.replace(" ", "")

        scores: dict[str, float] = {}

        for slug in self._slug_list:
            cat_tokens = self._cat_tokens[slug]
            cat_compact = self._cat_compact[slug]

            # --- TF overlap score ---
            # Count how many query tokens appear in the category document
            cat_token_set = set(cat_tokens)
            cat_tf: dict[str, int] = {}
            for t in cat_tokens:
                cat_tf[t] = cat_tf.get(t, 0) + 1
            total_cat_tokens = len(cat_tokens) or 1

            overlap_score = 0.0
            for qt in query_tokens:
                if qt in cat_tf:
                    # TF-weighted: more occurrences = higher weight category
                    tf_norm = math.log1p(cat_tf[qt]) / math.log1p(total_cat_tokens)
                    overlap_score += tf_norm

            if query_tokens:
                overlap_score /= len(query_tokens)

            # --- Compact fuzzy score ---
            # Handles "dienthoai" vs "dien thoai may tinh bang" compact
            compact_score = 0.0
            if len(query_compact_form) >= 4:
                # Direct compact substring match (fast path)
                if query_compact_form in cat_compact or cat_compact.startswith(query_compact_form):
                    compact_score = 0.95
                else:
                    # Fuzzy compare compact query vs compact category
                    fs = token_similarity(query_compact_form, cat_compact)
                    # Also check slug_norm prefix
                    slug_norm = self._cat_norms[slug]
                    slug_tokens = slug_norm.split()
                    # Check if compact query is close to compact of slug tokens only
                    slug_compact_short = "".join(slug_tokens[:3])  # first 3 slug tokens
                    fs2 = token_similarity(query_compact_form, slug_compact_short)
                    compact_score = max(fs, fs2)

            # --- Per-token fuzzy score ---
            # Each query token fuzzy-matched against category document tokens
            fuzzy_score = 0.0
            for qt in query_tokens:
                best = max((token_similarity(qt, ct) for ct in cat_token_set if abs(len(qt) - len(ct)) <= 3), default=0.0)
                fuzzy_score += best
            if query_tokens:
                fuzzy_score /= len(query_tokens)

            # --- Combined score ---
            # Weighted combination:
            #   overlap (TF) : highest weight → direct semantic match
            #   compact fuzzy: handles joined-word queries
            #   token fuzzy  : handles typos in individual tokens
            combined = (
                overlap_score * 0.50
                + compact_score * 0.35
                + fuzzy_score  * 0.15
            )
            scores[slug] = round(combined, 4)

        if not scores:
            return _null_match()

        best_slug = max(scores, key=lambda s: scores[s])
        best_score = scores[best_slug]

        # Determine result_type based on confidence thresholds
        if best_score >= THRESHOLD_HIGH:
            result_type = "category_locked"
        elif best_score >= THRESHOLD_MED:
            result_type = "category_preferred"
        else:
            result_type = "full_scan"

        # Sanity: only return a matched_category if we're actually confident
        matched = best_slug if result_type != "full_scan" else None

        return {
            "matched_category": matched,
            "confidence": best_score,
            "result_type": result_type,
            "all_scores": scores,
        }

    def get_category_norm(self, slug: str) -> str:
        """Return normalized form of a slug (for product filtering)."""
        return self._cat_norms.get(slug, normalize(slug.replace("-", " ")))

    def all_slugs(self) -> list[str]:
        return list(self._slug_list)


def _null_match() -> dict:
    return {
        "matched_category": None,
        "confidence": 0.0,
        "result_type": "full_scan",
        "all_scores": {},
    }
