# ============================================================
# DATA LOADER - Load JSON Data Files
# ============================================================

import json
import logging
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)

# SmartSearch integration (imported lazily to avoid circular deps)
try:
    from search_engine import SmartSearch
    _SMART_SEARCH_AVAILABLE = True
except ImportError:
    _SMART_SEARCH_AVAILABLE = False
    logger.warning("SmartSearch not available; falling back to legacy keyword search.")


class DataLoader:
    """
    Load and manage all JSON data files
    - products.json (2,980 products)
    - reviews.json (31,604 reviews)
    - timeseries.json (610 timeseries rows)
    """

    def __init__(self, data_dir: str = "./data"):
        """
        Initialize data loader

        Args:
            data_dir: Path to data directory containing JSON files
        """
        self.data_dir = Path(data_dir)
        self.products_df = None
        self.reviews_df = None
        self.timeseries_df = None
        self.raw_products_df = None
        self.url_by_product_id = {}
        self.urls_by_name = {}
        self.url_lookup_cache = {}
        self._smart_search: Optional["SmartSearch"] = None

        self._load_all()
        self._init_smart_search()

    def _load_all(self):
        """Load all data files"""
        import pandas as pd

        logger.info("📥 Loading data files...")

        # Load products
        products_path = self.data_dir / "products.json"
        if products_path.exists():
            with open(products_path, "r", encoding="utf-8") as f:
                products_data = json.load(f)
            self.products_df = pd.DataFrame(products_data)

            # Keep a raw-slug copy BEFORE display-name mapping
            # SmartSearch/CategoryMatcher needs raw slugs for semantic matching
            self._raw_slug_df = self.products_df.copy()

            # Standardize category names for UI display
            CATEGORY_MAPPING = {
                "dien-thoai-may-tinh-bang": "Điện thoại - Máy tính bảng",
                "laptop-may-tinh-bo":        "Laptop - Máy tính bộ",
                "thiet-bi-dien-tu":          "Thiết bị điện tử",
                "do-gia-dung":               "Đồ gia dụng",
                "thoi-trang-nam":            "Thời trang nam",
                "thoi-trang-nu":             "Thời trang nữ",
                "my-pham-lam-dep":           "Mỹ phẩm - Làm đẹp",
                "sach-truyen":               "Sách truyện",
                "the-thao-da-ngoai":         "Thể thao - Dã ngoại",
                "o-to-xe-may":               "Ô tô - Xe máy",
            }
            self._slug_to_display = CATEGORY_MAPPING  # keep for SmartSearch response mapping
            if not self.products_df.empty and "category" in self.products_df.columns:
                self.products_df["category"] = self.products_df["category"].map(
                    lambda x: CATEGORY_MAPPING.get(x, x)
                )

            # Create a leaf_category column representing the deepest non-null subcategory
            if not self.products_df.empty:
                category_levels = [f"category_level_{i}" for i in range(1, 13)]
                available_levels = [col for col in category_levels if col in self.products_df.columns]
                if available_levels:
                    # Clean up empty strings or whitespace to NaN first to allow ffill
                    temp_df = self.products_df[available_levels].replace(r'^\s*$', pd.NA, regex=True)
                    leaf_series = temp_df.ffill(axis=1).iloc[:, -1]
                    self.products_df["leaf_category"] = leaf_series.fillna(self.products_df["category"])
                else:
                    self.products_df["leaf_category"] = self.products_df["category"]
                
                # Double safety: clean up any nan strings or nulls
                self.products_df["leaf_category"] = self.products_df["leaf_category"].fillna(self.products_df["category"])
                self.products_df["leaf_category"] = self.products_df["leaf_category"].astype(str).str.strip()

            logger.info(f"   ✅ Loaded {len(self.products_df):,} products")
        else:
            logger.warning(f"   ⚠️  Products file not found: {products_path}")
            self.products_df = pd.DataFrame()

        # Load reviews
        reviews_path = self.data_dir / "reviews.json"
        reviews_csv_path = self.data_dir.parent / "new_data" / "Data" / "03_reviews.csv"
        if reviews_path.exists():
            with open(reviews_path, "r", encoding="utf-8") as f:
                reviews_data = json.load(f)
            self.reviews_df = pd.DataFrame(reviews_data)
            logger.info(f"   ✅ Loaded {len(self.reviews_df):,} reviews")
        elif reviews_csv_path.exists():
            logger.info(f"   📥 reviews.json not found. Loading and converting raw reviews from CSV: {reviews_csv_path}")
            try:
                # Load CSV using pandas
                df = pd.read_csv(reviews_csv_path)
                
                # Filter to only keep reviews for products we actually have to save memory
                if self.products_df is not None and not self.products_df.empty:
                    product_ids = set(self.products_df["product_id"].astype(str))
                    df["pid_str"] = df["product_id"].apply(DataLoader._safe_product_id)
                    df = df[df["pid_str"].isin(product_ids)].copy()
                    df = df.drop(columns=["pid_str"])
                
                # Standardize columns to match what main.py and search_engine_v2 expect
                # Fall back to title (e.g. "Cực kì hài lòng") if review content text is empty
                content_col = df["content"].fillna("").astype(str).str.strip()
                title_col = df["title"].fillna("").astype(str).str.strip() if "title" in df.columns else ""
                final_content = content_col.where(content_col != "", title_col)
                df["original_content"] = final_content
                df["cleaned_content"] = final_content
                
                # Add sentiment_label if not present
                if "sentiment_label" not in df.columns:
                    def get_sentiment(rating):
                        try:
                            r = int(float(rating))
                            return "positive" if r >= 4 else ("neutral" if r == 3 else "negative")
                        except (ValueError, TypeError):
                            return "positive"
                    df["sentiment_label"] = df["rating"].apply(get_sentiment)
                
                # Clean up product_id type using _safe_product_id
                df["product_id"] = df["product_id"].apply(DataLoader._safe_product_id)
                
                # Keep only necessary columns to minimize memory footprint
                cols_to_keep = ["review_id", "product_id", "rating", "original_content", "cleaned_content", "sentiment_label", "created_at"]
                cols_to_keep = [c for c in cols_to_keep if c in df.columns]
                self.reviews_df = df[cols_to_keep].copy()
                
                logger.info(f"   ✅ Successfully loaded and filtered {len(self.reviews_df):,} reviews from CSV")
            except Exception as e:
                logger.error(f"   ❌ Failed to load/process reviews CSV: {e}")
                self.reviews_df = pd.DataFrame()
        else:
            logger.warning(f"   ⚠️  Reviews file not found (JSON or CSV): {reviews_path}")
            self.reviews_df = pd.DataFrame()

        # Load timeseries
        timeseries_path = self.data_dir / "timeseries.json"
        if timeseries_path.exists():
            with open(timeseries_path, "r", encoding="utf-8") as f:
                timeseries_data = json.load(f)
            self.timeseries_df = pd.DataFrame(timeseries_data)
            if "ds" in self.timeseries_df.columns:
                self.timeseries_df["ds"] = pd.to_datetime(self.timeseries_df["ds"])
            logger.info(f"   ✅ Loaded {len(self.timeseries_df):,} timeseries rows")
        else:
            logger.warning(f"   ⚠️  Timeseries file not found: {timeseries_path}")
            self.timeseries_df = pd.DataFrame()

        # Load crawled raw CSV for URL resolution
        raw_products_path = self.data_dir / "tiki_products_raw.csv"
        if raw_products_path.exists():
            try:
                df_test = pd.read_csv(raw_products_path, nrows=0)
                if 'category_path_seed' in df_test.columns:
                    usecols = ["product_id", "name", "category_path_seed", "url_path"]
                    self.raw_products_df = pd.read_csv(raw_products_path, usecols=usecols)
                    self.raw_products_df = self.raw_products_df.rename(columns={"category_path_seed": "category"})
                else:
                    usecols = ["product_id", "name", "category", "url_path"]
                    self.raw_products_df = pd.read_csv(raw_products_path, usecols=usecols)
                self._build_url_indexes()
                logger.info(
                    f"   ✅ Loaded {len(self.raw_products_df):,} raw products for URL mapping"
                )
            except Exception as e:
                logger.warning(f"   ⚠️  Failed to load raw products CSV: {e}")
                self.raw_products_df = pd.DataFrame()
        else:
            logger.warning(f"   ⚠️  Raw products file not found: {raw_products_path}")
            self.raw_products_df = pd.DataFrame()

    def _init_smart_search(self) -> None:
        """Build SmartSearch index after data is loaded."""
        if not _SMART_SEARCH_AVAILABLE:
            return
        # Use raw-slug df so CategoryMatcher can use real slugs for semantic matching.
        # Fallback to products_df if raw copy doesn't exist.
        search_df = getattr(self, "_raw_slug_df", self.products_df)
        if search_df is None or search_df.empty:
            return
        try:
            self._smart_search = SmartSearch(
                products_df=search_df,
                resolve_url_fn=self.resolve_product_url,
                slug_to_display=getattr(self, "_slug_to_display", {}),
            )
            logger.info("   ✅ SmartSearch index ready")
        except Exception as exc:
            logger.warning(f"   ⚠️  SmartSearch init failed: {exc}; falling back to legacy search.")
            self._smart_search = None

    @staticmethod
    def _normalize_text(value: Any) -> str:
        """Normalize text for stable matching across accented/cased variants."""
        if value is None:
            return ""

        text = str(value).strip().lower()
        if not text:
            return ""

        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _safe_product_id(value: Any) -> str:
        """Convert product id from mixed source types to canonical string."""
        if value is None:
            return ""
        try:
            return str(int(float(value)))
        except (ValueError, TypeError):
            return str(value).strip()

    def _build_url_indexes(self):
        """Build indexes for fast URL resolution"""
        self.url_by_product_id = {}
        self.urls_by_name = {}

        if self.raw_products_df is None or self.raw_products_df.empty:
            return

        import pandas as pd
        for _, row in self.raw_products_df.iterrows():
            raw_url = row.get("url_path")
            if pd.isna(raw_url):
                continue

            url = str(raw_url).strip()
            if not url:
                continue

            if not url.startswith('http'):
                url = "https://tiki.vn/" + url.lstrip('/')

            pid = self._safe_product_id(row.get("product_id"))
            if pid:
                self.url_by_product_id[pid] = url

            name_norm = self._normalize_text(row.get("name"))
            if not name_norm:
                continue

            entry = {
                "url": url,
                "product_id": pid,
                "category_norm": self._normalize_text(row.get("category")),
                "name_norm": name_norm,
            }
            self.urls_by_name.setdefault(name_norm, []).append(entry)

    def resolve_product_url(
        self, product_id: Any, name: Any = None, category: Any = None
    ) -> str:
        """
        Resolve canonical Tiki product URL from crawled data.
        Priority: product_id -> exact normalized name -> fuzzy normalized name.
        """
        pid = self._safe_product_id(product_id)
        name_norm = self._normalize_text(name)
        category_norm = self._normalize_text(category)
        cache_key = (pid, name_norm, category_norm)

        if cache_key in self.url_lookup_cache:
            return self.url_lookup_cache[cache_key]

        # 1) Exact product_id match
        if pid and pid in self.url_by_product_id:
            url = self.url_by_product_id[pid]
            self.url_lookup_cache[cache_key] = url
            return url

        # 2) Exact normalized name match
        if name_norm and name_norm in self.urls_by_name:
            entries = self.urls_by_name[name_norm]
            if category_norm:
                for entry in entries:
                    if entry["category_norm"] == category_norm:
                        self.url_lookup_cache[cache_key] = entry["url"]
                        return entry["url"]

            url = entries[0]["url"]
            self.url_lookup_cache[cache_key] = url
            return url

        # 3) Fuzzy normalized name match (safety threshold)
        best_url = ""
        best_score = 0.0
        if name_norm and self.urls_by_name:
            query_tokens = set(name_norm.split())

            for candidate_name, entries in self.urls_by_name.items():
                ratio = SequenceMatcher(None, name_norm, candidate_name).ratio()

                if query_tokens:
                    cand_tokens = set(candidate_name.split())
                    overlap = len(query_tokens & cand_tokens) / max(
                        len(query_tokens), 1
                    )
                else:
                    overlap = 0.0

                score = (0.7 * ratio) + (0.3 * overlap)
                if score > best_score:
                    if category_norm:
                        category_entries = [
                            e for e in entries if e["category_norm"] == category_norm
                        ]
                        chosen = category_entries[0] if category_entries else entries[0]
                    else:
                        chosen = entries[0]

                    best_score = score
                    best_url = chosen["url"]

        if best_score >= 0.82 and best_url:
            self.url_lookup_cache[cache_key] = best_url
            return best_url

        # Final fallback for click-through continuity
        fallback_url = f"https://tiki.vn/p/{pid}" if pid else ""
        self.url_lookup_cache[cache_key] = fallback_url
        return fallback_url

    def get_products(self):
        """Get products DataFrame"""
        return self.products_df

    def get_reviews(self):
        """Get reviews DataFrame"""
        return self.reviews_df

    def get_timeseries(self):
        """Get timeseries DataFrame"""
        return self.timeseries_df

    def search_products(
        self, keyword: str, limit: int = 20, use_relevance_boost: bool = True, debug: bool = False
    ) -> List[Dict]:
        """
        Search products by keyword.
        Uses SmartSearch (BM25 + fuzzy + synonym expansion) when available,
        falls back to the legacy regex-based approach.

        Args:
            keyword:            Search keyword (with/without accent, may have typos).
            limit:              Max number of results.
            use_relevance_boost: Legacy param, kept for API compatibility.
            debug:              If True, attach '_debug' score breakdown to each product.

        Returns:
            List of product dictionaries sorted by relevance + sales.
        """
        if self.products_df is None or self.products_df.empty:
            return []

        # --- SmartSearch (new engine) ---
        if self._smart_search is not None:
            return self._smart_search.search(keyword=keyword, limit=limit, debug=debug)

        # --- Legacy fallback (old regex engine) ---
        logger.debug("search_products: using legacy regex engine")

        # Search in name and category
        keyword_lower = keyword.lower()
        keyword_words = keyword_lower.split()

        # Dùng word boundary (\b) để tránh match substring (vd: "xe" không match "Boxer")
        pattern = r"\b" + re.escape(keyword_lower) + r"\b"

        mask = self.products_df["name"].str.lower().str.contains(
            pattern, na=False, regex=True
        ) | self.products_df["category"].str.lower().str.contains(
            pattern, na=False, regex=True
        )

        results_df = self.products_df[mask].copy()

        # Fallback 1: Nếu không có kết quả khớp chính xác cụm từ, khớp tất cả các từ đơn lẻ trong từ khóa
        if results_df.empty and keyword_words:
            word_masks = []
            for word in keyword_words:
                escaped_word = re.escape(word)
                word_pattern = r"\b" + escaped_word + r"\b"
                word_mask = self.products_df["name"].str.lower().str.contains(word_pattern, na=False, regex=True) | \
                            self.products_df["category"].str.lower().str.contains(word_pattern, na=False, regex=True)
                word_masks.append(word_mask)
            
            if word_masks:
                combined_mask = word_masks[0]
                for m in word_masks[1:]:
                    combined_mask = combined_mask & m
                results_df = self.products_df[combined_mask].copy()

        # Fallback 2: Nếu khớp tất cả từ vẫn trống, cho phép khớp linh hoạt hơn không có \b (nửa từ, hoặc ký tự đặc biệt)
        if results_df.empty and keyword_words:
            word_masks = []
            for word in keyword_words:
                escaped_word = re.escape(word)
                word_mask = self.products_df["name"].str.lower().str.contains(escaped_word, na=False) | \
                            self.products_df["category"].str.lower().str.contains(escaped_word, na=False)
                word_masks.append(word_mask)
            
            if word_masks:
                combined_mask = word_masks[0]
                for m in word_masks[1:]:
                    combined_mask = combined_mask & m
                results_df = self.products_df[combined_mask].copy()

        if results_df.empty:
            return []

        # === RELEVANCE SCORING ===
        # Score products based on keyword match quality
        def calculate_relevance_score(row):
            title = str(row.get("name", "")).lower()
            score = 0

            # 1. Check hierarchical categories bottom-up
            # Prioritize matching in deeper category levels
            category_match_score = 0
            for level in range(12, 0, -1):
                cat_val = row.get(f"category_level_{level}")
                if pd.notna(cat_val) and cat_val != "":
                    cat_val_lower = str(cat_val).lower()
                    if re.search(pattern, cat_val_lower):
                        # The deeper the level, the higher the score.
                        # Level 12 -> 50, Level 1 -> 17 (roughly 50 - (12-level)*3)
                        category_match_score = 50 - ((12 - level) * 3)
                        break

            if category_match_score > 0:
                score += category_match_score
            else:
                # If no specific category matched, check the generic category field
                category = str(row.get("category", "")).lower()
                if re.search(pattern, category):
                    score += 10

            # 2. Check keyword in title
            # Title match adds points, but a deep category match still dominates
            if re.search(pattern, title):
                score += 5

            # 3. Count matching words (for multi-word searches)
            category_text = " ".join([str(row.get(f"category_level_{i}", "")) for i in range(1, 13) if pd.notna(row.get(f"category_level_{i}"))])
            text = f"{title} {category_text}".lower()
            matching_words = sum(1 for word in keyword_words if word in text)
            score += matching_words * 2

            return score

        results_df["relevance_score"] = results_df.apply(
            calculate_relevance_score, axis=1
        )

        # === COMBINED RANKING ===
        # Normalize quantity_sold for fair comparison
        max_quantity = results_df["quantity_sold"].max()
        results_df["quantity_norm"] = (
            (results_df["quantity_sold"] / max_quantity) if max_quantity > 0 else 0
        )

        # Detect if this is a specialized search (contains model/brand terms)
        # These searches should prioritize relevance over sales volume
        vehicle_keywords = [
            "xe",
            "oto",
            "o to",
            "xe may",
            "xemay",
            "xe dap",
            "xedap",
            "future",
            "vision",
            "pcx",
            "lead",
            "air blade",
        ]
        is_specialized_search = any(kw in keyword_lower for kw in vehicle_keywords)

        if use_relevance_boost and is_specialized_search:
            # For specialized searches: prioritize relevance (70%) over sales (30%)
            results_df["final_score"] = (results_df["relevance_score"] * 0.7) + (
                results_df["quantity_norm"] * 30
            )
        else:
            # For general searches: balanced approach (40% relevance, 60% sales)
            results_df["final_score"] = (results_df["relevance_score"] * 0.4) + (
                results_df["quantity_norm"] * 60
            )

        # Sort by final score (descending), then by quantity_sold as tiebreaker
        results_df = results_df.sort_values(
            ["final_score", "quantity_sold"], ascending=[False, False]
        )

        # Convert to list of dicts
        products = []
        for _, row in results_df.head(limit).iterrows():
            product_url = self.resolve_product_url(
                product_id=row.get("product_id"),
                name=row.get("name"),
                category=row.get("category"),
            )
            product_dict = {
                "product_id": str(row["product_id"]),
                "title": row["name"],
                "categoryName": row["category"],
                "price": float(row["original_price"]),
                "rating": float(row["original_rating"]),
                "boughtInLastMonth": int(row["quantity_sold"]),
                "estimated_revenue": float(
                    row["original_price"] * row["quantity_sold"]
                ),
                "product_url": product_url,
                "url_path": product_url,
            }
            # Add all available hierarchical categories
            for i in range(1, 13):
                cat_key = f"category_level_{i}"
                cat_val = row.get(cat_key)
                if pd.notna(cat_val) and cat_val != "":
                    product_dict[cat_key] = str(cat_val)
                    
            products.append(product_dict)

        return products

    def get_product_by_id(self, product_id: int) -> Dict:
        """Get single product by ID"""
        if self.products_df.empty:
            return {}

        product = self.products_df[self.products_df["product_id"] == product_id]
        if product.empty:
            return {}

        row = product.iloc[0]
        product_url = self.resolve_product_url(
            product_id=row.get("product_id"),
            name=row.get("name"),
            category=row.get("category"),
        )
        product_dict = {
            "product_id": str(row["product_id"]),
            "title": row["name"],
            "categoryName": str(row["category"]),
            "price": float(row["original_price"]),
            "rating": float(row["original_rating"]),
            "boughtInLastMonth": int(row["quantity_sold"]),
            "estimated_revenue": float(row["original_price"] * row["quantity_sold"]),
            "product_url": product_url,
            "url_path": product_url,
        }
        deepest_cat = product_dict["categoryName"]
        for i in range(1, 13):
            cat_key = f"category_level_{i}"
            cat_val = row.get(cat_key)
            if pd.notna(cat_val) and str(cat_val).strip() and str(cat_val).lower() != "nan":
                val = str(cat_val).strip()
                product_dict[cat_key] = val
                deepest_cat = val
        
        product_dict["categoryName"] = deepest_cat
        return product_dict

    def get_reviews_by_product(self, product_id: int):
        """Get all reviews for a product"""
        if self.reviews_df.empty:
            import pandas as pd

            return pd.DataFrame()

        return self.reviews_df[self.reviews_df["product_id"] == product_id]

    def get_stats(self) -> Dict[str, Any]:
        """Get data statistics"""
        return {
            "total_products": len(self.products_df),
            "total_reviews": len(self.reviews_df),
            "total_timeseries_rows": len(self.timeseries_df),
            "data_loaded": not self.products_df.empty,
        }
