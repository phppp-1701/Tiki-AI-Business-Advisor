import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple


def _norm(value: Any) -> str:
    """Normalize text: remove accents, lowercase, keep alphanumeric + spaces."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    if not text:
        return ""
    # Handle đ/Đ explicitly (NFD doesn't decompose it)
    text = text.replace("đ", "d").replace("Đ", "d")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# ============================================================
# CANONICAL INTENT MAP
# Maps normalized query variants → (canonical_label, context_hint)
# canonical_label: label đẹp có dấu hiển thị trên UI
# context_hint: gợi ý context_id ưu tiên (override fallback)
# ============================================================
_CANONICAL_INTENTS: Dict[str, Dict[str, str]] = {
    # === Điện thoại ===
    "dien thoai":              {"label": "điện thoại", "context": "product"},
    "dien thoai thong minh":   {"label": "điện thoại thông minh", "context": "product"},
    "smartphone":              {"label": "điện thoại", "context": "product"},
    "phone":                   {"label": "điện thoại", "context": "product"},
    "mobile":                  {"label": "điện thoại", "context": "product"},
    "dt":                      {"label": "điện thoại", "context": "product"},
    # === Máy tính bảng ===
    "may tinh bang":           {"label": "máy tính bảng", "context": "product"},
    "tablet":                  {"label": "máy tính bảng", "context": "product"},
    "ipad":                    {"label": "iPad", "context": "product"},
    # === Laptop ===
    "laptop":                  {"label": "laptop", "context": "product"},
    "may tinh xach tay":       {"label": "máy tính xách tay", "context": "product"},
    "notebook":                {"label": "laptop", "context": "product"},
    # === Tai nghe ===
    "tai nghe":                {"label": "tai nghe", "context": "product"},
    "tai nghe bluetooth":      {"label": "tai nghe bluetooth", "context": "product"},
    "tai nghe chong on":       {"label": "tai nghe chống ồn", "context": "product"},
    "headphone":               {"label": "tai nghe", "context": "product"},
    "earphone":                {"label": "tai nghe", "context": "product"},
    "earbuds":                 {"label": "tai nghe", "context": "product"},
    # === TV / Màn hình ===
    "tivi":                    {"label": "tivi", "context": "product"},
    "man hinh":                {"label": "màn hình", "context": "product"},
    "monitor":                 {"label": "màn hình", "context": "product"},
    # === Thời trang ===
    "ao thun":                 {"label": "áo thun", "context": "product"},
    "ao thun nam":             {"label": "áo thun nam", "context": "product"},
    "ao thun nu":              {"label": "áo thun nữ", "context": "product"},
    "ao phong":                {"label": "áo phông", "context": "product"},
    "ao phong nam":            {"label": "áo phông nam", "context": "product"},
    "quan jean":               {"label": "quần jean", "context": "product"},
    "jeans":                   {"label": "quần jean", "context": "product"},
    "vay":                     {"label": "váy", "context": "product"},
    "chan vay":                 {"label": "chân váy", "context": "product"},
    "dam nu":                  {"label": "đầm nữ", "context": "product"},
    "giay the thao":           {"label": "giày thể thao", "context": "product"},
    "sneaker":                 {"label": "giày thể thao", "context": "product"},
    # === Sách ===
    "sach":                    {"label": "sách", "context": "book"},
    "truyen tranh":            {"label": "truyện tranh", "context": "book"},
    "manga":                   {"label": "manga / truyện tranh", "context": "book"},
    "comic":                   {"label": "truyện tranh", "context": "book"},
    # === Xe / Phương tiện ===
    "xe may":                  {"label": "xe máy", "context": "vehicle"},
    "o to":                    {"label": "ô tô", "context": "vehicle"},
    "xe dap":                  {"label": "xe đạp", "context": "vehicle"},
    # === Skincare / Mỹ phẩm ===
    "son moi":                 {"label": "son môi", "context": "product"},
    "lipstick":                {"label": "son môi", "context": "product"},
    "sua rua mat":             {"label": "sữa rửa mặt", "context": "product"},
    "kem chong nang":          {"label": "kem chống nắng", "context": "product"},
    "sunscreen":               {"label": "kem chống nắng", "context": "product"},
    "serum":                   {"label": "serum", "context": "product"},
    "kem duong am":            {"label": "kem dưỡng ẩm", "context": "product"},
    # === Gia dụng ===
    "noi com dien":            {"label": "nồi cơm điện", "context": "product"},
    # === Thể thao ===
    "giay chay bo":            {"label": "giày chạy bộ", "context": "product"},
}


def resolve_canonical(keyword: str) -> Dict[str, str] | None:
    """
    Given a raw keyword, return its canonical info dict if found.
    Returns: {"label": "...", "context": "..."} or None.

    Matching order:
    1. Exact normalized match
    2. Prefix match (longest first)
    """
    kw_norm = _norm(keyword)
    if not kw_norm:
        return None
    # Exact match
    if kw_norm in _CANONICAL_INTENTS:
        return _CANONICAL_INTENTS[kw_norm]
    # Longest prefix match
    best_key = ""
    for key in _CANONICAL_INTENTS:
        if kw_norm.startswith(key) or key.startswith(kw_norm):
            if len(key) > len(best_key):
                best_key = key
    if best_key:
        return _CANONICAL_INTENTS[best_key]
    return None


def _contains_any(haystack: str, needles: List[str]) -> bool:
    return any(n in haystack for n in needles)


def detectContext(product: Dict[str, Any], keyword: str) -> str:
    """
    Classify a product by its deepest available category level.
    This replaces the old heuristic logic and ensures context suggestions
    are exactly the smallest child branch categories.
    """
    # Find the deepest category level (12 down to 1)
    for i in range(12, 0, -1):
        cat_key = f"category_level_{i}"
        cat_val = product.get(cat_key)
        if cat_val and str(cat_val).strip() and str(cat_val).lower() != "nan":
            return str(cat_val).strip()

    # Fallback to general category name
    cat_val = product.get("categoryName") or product.get("category")
    if cat_val and str(cat_val).strip() and str(cat_val).lower() != "nan":
        return str(cat_val).strip()

    return "Sản phẩm khác"


def groupByContext(
    products: List[Dict[str, Any]], keyword: str
) -> Dict[str, List[Dict[str, Any]]]:
    """Group products by their deepest category."""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for p in products or []:
        ctx = detectContext(p, keyword)
        grouped.setdefault(ctx, []).append(p)
    return grouped


def _context_label(keyword: str, context_id: str) -> str:
    """
    Since context_id is now simply the category name (e.g., 'Thời trang nữ'),
    we just return it as the label.
    """
    return context_id


def getContextLabel(keyword: str, context_id: str) -> str:
    return _context_label(keyword, context_id)


def getSuggestedContexts(
    keyword: str,
    grouped: Dict[str, List[Dict[str, Any]]],
    selected_context: str,
    max_suggestions: int = 6,
) -> List[Dict[str, Any]]:
    """
    Suggest alternative categories that contain products for the search keyword.
    We just suggest the largest category buckets.
    """
    from search_engine.normalizer import normalize
    kw_norm = f" {normalize(keyword)} "
    
    # Extract core keyword for "A cho B" queries
    core_kw = kw_norm.strip()
    if " cho " in f" {core_kw} ":
        core_kw = f" {core_kw} ".split(" cho ")[0].strip()
    elif " danh cho " in f" {core_kw} ":
        core_kw = f" {core_kw} ".split(" danh cho ")[0].strip()
        
    accessory_keywords = ["op lung", "bao da", "mieng dan", "phu kien", "cap", "sac", "tai nghe", "day", "adapter", "vo"]
    is_searching_accessory = any(f" {ack} " in kw_norm for ack in accessory_keywords)

    scored_counts = []
    for ctx, items in grouped.items():
        if ctx == selected_context or len(items) < 1 or ctx == "Sản phẩm khác":
            continue
            
        count = len(items)
        score = float(count)
        ctx_norm = f" {normalize(ctx)} "

        if core_kw and core_kw in ctx_norm:
            score *= 5.0
            
        if not is_searching_accessory and any(f" {ack} " in ctx_norm for ack in accessory_keywords):
            score *= 0.1
            
        scored_counts.append((ctx, count, score))

    # Sort by smart score descending
    scored_counts.sort(key=lambda x: -x[2])

    suggestions = []
    for ctx, cnt, _ in scored_counts:
        bucket_products = grouped.get(ctx, [])
        evidence_examples = [
            str(p.get("title", p.get("name", "")))[:60]
            for p in bucket_products[:3]
        ]

        suggestions.append({
            "context_id":            ctx,
            "label":                 _context_label(keyword, ctx),
            "count":                 cnt,
            "is_template_generated": False,
            "is_validated_by_data":  True,
            "evidence_count":        len(bucket_products),
            "evidence_examples":     evidence_examples,
        })
        
        if len(suggestions) >= max_suggestions:
            break

    return suggestions


def pick_primary_context(grouped: Dict[str, List[Dict[str, Any]]], keyword: str = "") -> str:
    """
    Pick the category that contains the most products, but with smart heuristics.
    Penalizes accessory categories (cases, screen protectors) unless specifically searched for.
    Boosts categories that contain the exact keyword.
    """
    if not grouped:
        return "Sản phẩm khác"

    from search_engine.normalizer import normalize
    kw_norm = f" {normalize(keyword)} "
    
    # Extract core keyword for "A cho B" queries (e.g. "váy cho nam" -> core is "váy")
    core_kw = kw_norm.strip()
    if " cho " in f" {core_kw} ":
        core_kw = f" {core_kw} ".split(" cho ")[0].strip()
    elif " danh cho " in f" {core_kw} ":
        core_kw = f" {core_kw} ".split(" danh cho ")[0].strip()
    
    # Identify if user is specifically searching for accessories
    accessory_keywords = ["op lung", "bao da", "mieng dan", "phu kien", "cap", "sac", "tai nghe", "day", "adapter", "vo"]
    is_searching_accessory = any(f" {ack} " in kw_norm for ack in accessory_keywords)

    scored_contexts = []
    for ctx, items in grouped.items():
        count = len(items)
        score = float(count)
        ctx_norm = f" {normalize(ctx)} "

        # 1. Boost if context name contains the core keyword
        if core_kw and core_kw in ctx_norm:
            score *= 5.0
            
        # 2. Penalize accessory categories if user didn't search for them
        if not is_searching_accessory:
            if any(f" {ack} " in ctx_norm for ack in accessory_keywords):
                score *= 0.1  # Heavily penalize to prioritize main products
                
        scored_contexts.append((ctx, score))

    # Sort by score to find the best
    sorted_by_score = sorted(scored_contexts, key=lambda x: x[1], reverse=True)
    return sorted_by_score[0][0]


def filter_by_context(
    products: List[Dict[str, Any]], keyword: str, context_id: str
) -> List[Dict[str, Any]]:
    if not context_id:
        return products or []
    return [p for p in (products or []) if detectContext(p, keyword) == context_id]
