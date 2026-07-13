# ============================================================
# NORMALIZER — Vietnamese Text Normalization (v2)
# Handles:
#   - Unicode NFC normalization
#   - Diacritic removal (no-accent form) via unicodedata NFD
#   - Lowercase + whitespace cleanup
#   - Joined-word splitting (dienthoai → dien thoai)
#   - Query alias / canonical mapping (smartphone → dien thoai)
# ============================================================

import re
import unicodedata
from functools import lru_cache


@lru_cache(maxsize=8192)
def remove_accents(text: str) -> str:
    """Remove Vietnamese diacritics, return ASCII-only lowercased string."""
    if not text:
        return ""
    # NFD decomposes accented chars into base char + combining marks
    plain = unicodedata.normalize("NFD", text.lower())
    # Strip all combining marks (diacritics)
    plain = "".join(ch for ch in plain if unicodedata.category(ch) != "Mn")
    # Handle đ/Đ explicitly (not decomposed by NFD)
    plain = plain.replace("đ", "d").replace("ð", "d")
    return plain


@lru_cache(maxsize=8192)
def has_diacritics(text: str) -> bool:
    """
    Return True if text contains any Vietnamese diacritic character (accent mark).
    Used to distinguish:
      - "vay"  (no accents) → user didn't specify → normalize freely
      - "váy"  (has accent) → user was specific → match on original accented form
      - "điên thoại" (has accents but wrong) → normalize+fuzzy only if no exact match
    """
    if not text:
        return False
    nfc = unicodedata.normalize("NFC", text)
    for ch in nfc:
        # Check if NFD decomposition has combining marks (diacritics)
        nfd = unicodedata.normalize("NFD", ch)
        if len(nfd) > 1 and any(unicodedata.category(c) == "Mn" for c in nfd):
            return True
        # đ/Đ are not decomposed by NFD but are diacritics
        if ch in ("đ", "Đ"):
            return True
    return False


@lru_cache(maxsize=8192)
def accent_lower(text: str) -> str:
    """
    Lowercase text while PRESERVING Vietnamese diacritics.
    Used for accent-aware exact matching when user typed with accents.
    Example: "Chân Váy Xòe" → "chân váy xòe"
    """
    if not text:
        return ""
    return unicodedata.normalize("NFC", text).lower()


@lru_cache(maxsize=8192)
def normalize(text: str) -> str:
    """
    Full normalization pipeline:
      1. NFC Unicode normalization
      2. Lowercase
      3. Remove diacritics → ASCII (NFD method)
      4. Keep only alphanumeric, collapse whitespace
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = remove_accents(text)
    # Replace non-alphanumeric with space
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def tokenize(text: str) -> list[str]:
    """Normalize and split into tokens, filtering empty strings."""
    return [t for t in normalize(text).split() if t]


# ------------------------------------------------------------------
# Alias / canonical mapping
# Maps common joined/typo variants → canonical spaced form.
# IMPORTANT: keys are already normalized (no diacritics, lowercase).
# These are only applied at the query pre-processing stage.
# ------------------------------------------------------------------
_QUERY_ALIASES: dict[str, str] = {
    # Electronics — joined words
    "dienthoai":        "dien thoai",
    "smartphone":       "dien thoai",
    "mobile":           "dien thoai",
    "phone":            "dien thoai",
    "tainghe":          "tai nghe",
    "headphone":        "tai nghe",
    "earphone":         "tai nghe",
    "laptop":           "may tinh xach tay",
    "notebook":         "may tinh xach tay",
    "maytinh":          "may tinh",
    "maytinhxachtay":   "may tinh xach tay",
    "maytinhbang":      "may tinh bang",
    "tablet":           "may tinh bang",
    "ipad":             "may tinh bang",

    # Books
    "truyentranh":      "truyen tranh",
    "manga":            "truyen tranh",
    "comic":            "truyen tranh",

    # Fashion
    "aothun":           "ao thun",
    "aophong":          "ao phong",
    "quanjean":         "quan jean",
    "jeans":            "quan jean",
    "sneaker":          "giay the thao",
    "giaytheothao":     "giay the thao",

    # Beauty
    "sonmoi":           "son moi",
    "lipstick":         "son moi",
    "cleanser":         "sua rua mat",
    "sunscreen":        "kem chong nang",
    "moisturizer":      "kem duong am",

    # Home
    "noicomdien":       "noi com dien",

    # Vehicle
    "xemay":            "xe may",
    "xedap":            "xe dap",
    "oto":              "o to",
}


def apply_query_aliases(normalized_query: str) -> str:
    """
    Apply alias mapping to a normalized (no-accent) query.
    Checks exact match first, then token-level substitution.
    Returns the (possibly rewritten) query string.
    """
    if not normalized_query:
        return normalized_query

    # 1. Exact full-query alias
    if normalized_query in _QUERY_ALIASES:
        return _QUERY_ALIASES[normalized_query]

    # 2. Token-level substitution — replace tokens that are known aliases
    tokens = normalized_query.split()
    new_tokens: list[str] = []
    i = 0
    while i < len(tokens):
        # Try bigram first
        if i + 1 < len(tokens):
            bigram = tokens[i] + tokens[i + 1]
            if bigram in _QUERY_ALIASES:
                new_tokens.extend(_QUERY_ALIASES[bigram].split())
                i += 2
                continue
        # Single token
        tok = tokens[i]
        if tok in _QUERY_ALIASES:
            new_tokens.extend(_QUERY_ALIASES[tok].split())
        else:
            new_tokens.append(tok)
        i += 1

    return " ".join(new_tokens)


def preprocess_query(raw: str) -> str:
    """
    Full query pre-processing pipeline:
      1. Normalize (remove accents, lowercase, clean)
      2. Apply alias / canonical mapping
      3. Collapse extra whitespace
    Returns a clean, canonical query string ready for search.
    """
    normed = normalize(raw)
    canonical = apply_query_aliases(normed)
    return re.sub(r"\s+", " ", canonical).strip()


def build_search_doc(name: str, category: str, brand: str = "", description: str = "") -> str:
    """
    Build a weighted search document from product fields.
    Name and category are repeated to boost their TF weight in BM25.
    """
    parts = []
    # name × 3 (highest weight)
    name_norm = normalize(name)
    if name_norm:
        parts.extend([name_norm] * 3)
    # category × 2
    cat_norm = normalize(category)
    if cat_norm:
        parts.extend([cat_norm] * 2)
    # brand × 2
    brand_norm = normalize(brand)
    if brand_norm:
        parts.extend([brand_norm] * 2)
    # description × 1
    desc_norm = normalize(description)
    if desc_norm:
        parts.append(desc_norm)
    return " ".join(parts)
