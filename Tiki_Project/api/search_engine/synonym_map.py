# ============================================================
# SYNONYM MAP — Vietnamese E-commerce Query Expansion (v2)
#
# Hai loại mapping:
#
# 1. COMPOUND_PHRASES (QUAN TRỌNG NHẤT)
#    - Nhận diện cụm từ ghép CÓ Ý NGHĨA RIÊNG
#    - Mỗi cụm có: synonyms (mở rộng tìm kiếm) + category_focus (ưu tiên category)
#    - Token trong cụm KHÔNG được expand độc lập khi query match cụm này
#
# 2. _RAW_SYNONYMS (mở rộng đơn từ / cụm thông thường)
#    - Chỉ dùng khi query KHÔNG match compound phrase nào
#
# REAL CATEGORIES in data (9 total):
#   dien-thoai-may-tinh-bang
#   do-gia-dung
#   my-pham-lam-dep
#   o-to-xe-may
#   sach-truyen
#   the-thao-da-ngoai
#   thiet-bi-dien-tu
#   thoi-trang-nam
#   thoi-trang-nu
# ============================================================

from .normalizer import normalize


# ------------------------------------------------------------------
# COMPOUND PHRASES — cụm từ ghép có ý nghĩa riêng
# category_focus: dùng SLUG thật từ data (đã normalize sẽ thành dạng no-accent)
# ------------------------------------------------------------------
_RAW_COMPOUNDS: dict[str, dict] = {
    # === Sách / Truyện ===
    "truyen tranh": {
        "synonyms": ["comic", "manga", "truyen tranh"],
        "category_focus": ["sach-truyen"],
        "description": "Truyện tranh, manga, comic",
    },
    "sach giao khoa": {
        "synonyms": ["giao trinh", "sach hoc", "textbook"],
        "category_focus": ["sach-truyen"],
        "description": "Sách giáo khoa",
    },
    "sach day nau an": {
        "synonyms": ["cookbook", "nau nuong"],
        "category_focus": ["sach-truyen"],
        "description": "Sách dạy nấu ăn",
    },
    "sach": {
        "synonyms": ["book", "truyen", "sach truyen"],
        "category_focus": ["sach-truyen"],
        "description": "Sách",
    },

    # === Điện thoại ===
    "dien thoai thong minh": {
        "synonyms": ["smartphone", "dien thoai", "mobile"],
        "category_focus": ["dien-thoai-may-tinh-bang"],
        "description": "Điện thoại thông minh",
    },
    "dien thoai": {
        "synonyms": ["smartphone", "mobile", "phone"],
        "category_focus": ["dien-thoai-may-tinh-bang"],
        "description": "Điện thoại",
    },
    "may tinh bang": {
        "synonyms": ["tablet", "ipad"],
        "category_focus": ["dien-thoai-may-tinh-bang"],
        "description": "Máy tính bảng",
    },

    # === Skincare ===
    "sua rua mat": {
        "synonyms": ["face wash", "cleanser", "gel rua mat"],
        "category_focus": ["my-pham-lam-dep"],
        "description": "Sữa rửa mặt",
    },
    "kem chong nang": {
        "synonyms": ["sunscreen", "sunblock", "spf"],
        "category_focus": ["my-pham-lam-dep"],
        "description": "Kem chống nắng",
    },
    "kem duong am": {
        "synonyms": ["moisturizer", "kem duong"],
        "category_focus": ["my-pham-lam-dep"],
        "description": "Kem dưỡng ẩm",
    },
    "mat na duong da": {
        "synonyms": ["face mask", "sheet mask"],
        "category_focus": ["my-pham-lam-dep"],
        "description": "Mặt nạ dưỡng da",
    },
    "son moi": {
        "synonyms": ["lipstick", "lip gloss", "son moi lipstick"],  # 'son' alone too ambiguous
        "category_focus": ["my-pham-lam-dep"],
        "description": "Son môi",
    },
    "nuoc tay trang": {
        "synonyms": ["makeup remover", "tay trang"],
        "category_focus": ["my-pham-lam-dep"],
        "description": "Nước tẩy trang",
    },
    "my pham": {
        "synonyms": ["beauty", "skincare", "cosmetic"],
        "category_focus": ["my-pham-lam-dep"],
        "description": "Mỹ phẩm",
    },

    # === Fashion — nam ===
    "ao thun nam": {
        "synonyms": ["t shirt nam", "ao phong nam", "ao nam"],
        "category_focus": ["thoi-trang-nam"],
        "description": "Áo thun nam",
    },
    "quan jean nam": {
        "synonyms": ["jeans nam", "quan bo nam", "denim nam"],
        "category_focus": ["thoi-trang-nam"],
        "description": "Quần jean nam",
    },
    "ao khoac nam": {
        "synonyms": ["jacket nam", "hoodie nam"],
        "category_focus": ["thoi-trang-nam"],
        "description": "Áo khoác nam",
    },
    "thoi trang nam": {
        "synonyms": ["do nam", "quan ao nam"],
        "category_focus": ["thoi-trang-nam"],
        "description": "Thời trang nam",
    },

    # === Fashion — nữ ===
    "ao thun nu": {
        "synonyms": ["t shirt nu", "ao phong nu", "ao nu"],
        "category_focus": ["thoi-trang-nu"],
        "description": "Áo thun nữ",
    },
    "dam nu": {
        "synonyms": ["dress", "vay dam nu"],
        "category_focus": ["thoi-trang-nu"],
        "description": "Đầm nữ",
    },
    "chan vay": {
        "synonyms": ["skirt", "vay"],
        "category_focus": ["thoi-trang-nu"],
        "description": "Chân váy",
    },
    "vay": {
        "synonyms": ["skirt", "dam nu", "chan vay"],
        "category_focus": ["thoi-trang-nu"],
        "description": "Váy",
    },
    "thoi trang nu": {
        "synonyms": ["do nu", "quan ao nu"],
        "category_focus": ["thoi-trang-nu"],
        "description": "Thời trang nữ",
    },

    # === Điện tử ===
    "tai nghe bluetooth": {
        "synonyms": ["bluetooth headphone", "tai nghe khong day", "wireless earphone"],
        "category_focus": ["thiet-bi-dien-tu", "dien-thoai-may-tinh-bang"],
        "description": "Tai nghe bluetooth",
    },
    "tai nghe chong on": {
        "synonyms": ["noise cancelling", "anc headphone", "tai nghe anc"],
        "category_focus": ["thiet-bi-dien-tu"],
        "description": "Tai nghe chống ồn",
    },
    "tai nghe": {
        "synonyms": ["headphone", "earphone", "earbuds"],
        "category_focus": ["thiet-bi-dien-tu", "dien-thoai-may-tinh-bang"],
        "description": "Tai nghe",
    },
    "may tinh xach tay": {
        "synonyms": ["laptop may tinh xach tay", "notebook may tinh"],  # use phrase, not 'laptop' alone
        "category_focus": ["thiet-bi-dien-tu"],
        "description": "Máy tính xách tay",
    },
    "loa bluetooth": {
        "synonyms": ["bluetooth speaker", "loa khong day"],
        "category_focus": ["thiet-bi-dien-tu"],
        "description": "Loa bluetooth",
    },
    "may giat": {
        "synonyms": ["washing machine"],
        "category_focus": ["thiet-bi-dien-tu"],
        "description": "Máy giặt",
    },

    # === Ô tô — Xe máy ===
    "phu kien xe may": {
        "synonyms": ["xe may accessory", "do xe may"],
        "category_focus": ["o-to-xe-may"],
        "description": "Phụ kiện xe máy",
    },
    "dau nhot xe may": {
        "synonyms": ["nhot xe may", "mo xe may", "engine oil"],
        "category_focus": ["o-to-xe-may"],
        "description": "Dầu nhớt xe máy",
    },
    "xe may": {
        "synonyms": ["scooter", "motor", "motorbike"],
        "category_focus": ["o-to-xe-may"],
        "description": "Xe máy",
    },
    "o to": {
        "synonyms": ["car", "automobile", "xe hoi"],
        "category_focus": ["o-to-xe-may"],
        "description": "Ô tô",
    },
    "xe dap": {
        "synonyms": ["bicycle", "bike"],
        "category_focus": ["the-thao-da-ngoai", "o-to-xe-may"],
        "description": "Xe đạp",
    },

    # === Thể thao ===
    "giay chay bo": {
        "synonyms": ["running shoe", "giay the thao chay"],
        "category_focus": ["the-thao-da-ngoai"],
        "description": "Giày chạy bộ",
    },
    "giay the thao": {
        "synonyms": ["sneaker", "sport shoe", "running shoe"],
        "category_focus": ["the-thao-da-ngoai", "thoi-trang-nam", "thoi-trang-nu"],
        "description": "Giày thể thao",
    },
    "do the thao": {
        "synonyms": ["sportswear", "trang phuc the thao", "gym wear"],
        "category_focus": ["the-thao-da-ngoai"],
        "description": "Đồ thể thao",
    },
    "the thao": {
        "synonyms": ["sport", "fitness"],
        "category_focus": ["the-thao-da-ngoai"],
        "description": "Thể thao",
    },

    # === Gia dụng ===
    "noi com dien": {
        "synonyms": ["rice cooker", "noi co"],
        "category_focus": ["do-gia-dung"],
        "description": "Nồi cơm điện",
    },
    "may loc nuoc": {
        "synonyms": ["water purifier", "loc nuoc"],
        "category_focus": ["do-gia-dung"],
        "description": "Máy lọc nước",
    },
    "may rua bat": {
        "synonyms": ["dishwasher"],
        "category_focus": ["do-gia-dung"],
        "description": "Máy rửa bát",
    },
    "do gia dung": {
        "synonyms": ["home appliance", "household"],
        "category_focus": ["do-gia-dung"],
        "description": "Đồ gia dụng",
    },
}

# ------------------------------------------------------------------
# Normalize compound phrases
# ------------------------------------------------------------------
COMPOUND_PHRASES: dict[str, dict] = {}
for _raw_phrase, _info in _RAW_COMPOUNDS.items():
    _norm_key = normalize(_raw_phrase)
    COMPOUND_PHRASES[_norm_key] = {
        "synonyms": [normalize(s) for s in _info["synonyms"]],
        "category_focus": [normalize(c) for c in _info["category_focus"]],
        "description": _info.get("description", ""),
        "raw_phrase": _raw_phrase,
    }

# ------------------------------------------------------------------
# REAL CATEGORY SLUG → normalized mapping (for category matching)
# Only real slugs from data — 9 total
# ------------------------------------------------------------------
REAL_CATEGORY_SLUGS: dict[str, str] = {
    "dien-thoai-may-tinh-bang": normalize("dien-thoai-may-tinh-bang"),
    "do-gia-dung":              normalize("do-gia-dung"),
    "my-pham-lam-dep":          normalize("my-pham-lam-dep"),
    "o-to-xe-may":              normalize("o-to-xe-may"),
    "sach-truyen":              normalize("sach-truyen"),
    "the-thao-da-ngoai":        normalize("the-thao-da-ngoai"),
    "thiet-bi-dien-tu":         normalize("thiet-bi-dien-tu"),
    "thoi-trang-nam":           normalize("thoi-trang-nam"),
    "thoi-trang-nu":            normalize("thoi-trang-nu"),
}

# ------------------------------------------------------------------
# Context keywords for "A cho B" query parsing
# ------------------------------------------------------------------
CONTEXT_KEYWORDS = [
    "cho", "danh cho", "cho nguoi", "cho ban",
    "nam", "nu", "cho nam", "cho nu",
    "tre em", "em be", "nguoi gia", "cho cho", "cho meo",
    "van phong", "di hoc", "du lich", "the thao",
    "nguoi khuyet tat", "nguoi benh",
]


def detect_compound(query_norm: str) -> dict | None:
    """
    Check if the normalized query matches a known compound phrase.
    Returns the compound info dict, or None if not found.
    Checks exact match, then longest-substring.
    """
    # Exact match
    if query_norm in COMPOUND_PHRASES:
        info = dict(COMPOUND_PHRASES[query_norm])
        info["matched_phrase"] = query_norm
        return info

    # Substring match: query contains a known compound (longest match wins)
    best: dict | None = None
    best_len = 0
    best_phrase = ""
    for phrase, info in COMPOUND_PHRASES.items():
        if phrase in query_norm and len(phrase) > best_len:
            best = dict(info)
            best_phrase = phrase
            best_len = len(phrase)
            
    if best:
        best["matched_phrase"] = best_phrase
    return best


def detect_context_query(query_norm: str) -> dict | None:
    """
    Detect "A cho B" / "A dành cho B" style queries.
    Returns dict with keys:
      - main_product: normalized main search term
      - context_term: normalized context modifier
    or None if not a context query.
    """
    # Pattern: main_product (cho|danh cho|nam|nu|tre em|...) context_term
    cho_patterns = [
        r"^(.+?)\s+danh\s+cho\s+(.+)$",
        r"^(.+?)\s+cho\s+(.+)$",
        r"^(.+?)\s+(nam|nu|tre\s*em|em\s*be|nguoi\s*gia|van\s*phong|du\s*lich|the\s*thao)$",
    ]
    for pattern in cho_patterns:
        import re
        m = re.match(pattern, query_norm.strip())
        if m:
            main = m.group(1).strip()
            context = m.group(2).strip()
            # Only trigger if main_product is non-trivial (>= 2 chars)
            if len(main) >= 2:
                return {"main_product": main, "context_term": context}
    return None


# ------------------------------------------------------------------
# Simple synonym dictionary (used when no compound phrase matches)
# ------------------------------------------------------------------
_RAW_SYNONYMS: dict[str, list[str]] = {
    # Electronics
    "dien thoai":    ["smartphone", "mobile", "phone"],
    "smartphone":    ["dien thoai", "mobile"],
    "laptop":        ["may tinh xach tay", "notebook"],
    "may tinh xach tay": ["laptop", "notebook"],
    "tai nghe":      ["headphone", "earphone", "earbuds"],
    "headphone":     ["tai nghe"],
    "earphone":      ["tai nghe"],
    "loa":           ["speaker"],
    "speaker":       ["loa"],
    "man hinh":      ["monitor", "display"],
    "monitor":       ["man hinh"],
    "ban phim":      ["keyboard"],
    "keyboard":      ["ban phim"],
    "chuot":         ["mouse"],
    "mouse":         ["chuot"],
    "camera":        ["may anh"],
    "may anh":       ["camera"],

    # Beauty (single-token fallback — compound takes priority)
    "lipstick":      ["son moi"],
    "cleanser":      ["sua rua mat"],
    "sunscreen":     ["kem chong nang"],
    "serum":         ["tinh chat"],
    "tinh chat":     ["serum"],
    "son":           ["son moi"],

    # Fashion
    "ao thun":       ["ao phong", "t shirt"],
    "ao phong":      ["ao thun", "t shirt"],
    "quan jean":     ["jeans", "denim"],
    "jeans":         ["quan jean", "denim"],
    "vay":           ["skirt", "dam"],
    "dam":           ["dress", "vay"],
    "dress":         ["dam", "vay"],
    "sneaker":       ["giay the thao"],
    "giay":          ["giay the thao", "sneaker"],
    "balo":          ["backpack"],
    "backpack":      ["balo"],
    "tui xach":      ["handbag", "bag"],

    # Books
    "sach":          ["book", "truyen"],
    "book":          ["sach"],
    "truyen":        ["sach"],
    "manga":         ["truyen tranh", "comic"],
    "comic":         ["truyen tranh", "manga"],

    # Home
    "noi":           ["pot"],

    # Sports
    "xe dap":        ["bicycle", "bike"],
    "bong da":       ["football", "soccer"],

    # Pets
    "thu cung":      ["pet"],
    "cho":           ["dog"],  # This is "chó" (dog), careful with stopword collision
}


def _build_synonym_index() -> dict[str, list[str]]:
    """Build bidirectional normalized synonym index."""
    index: dict[str, list[str]] = {}
    for raw_key, raw_vals in _RAW_SYNONYMS.items():
        key = normalize(raw_key)
        vals = [normalize(v) for v in raw_vals]
        existing = index.setdefault(key, [])
        for v in vals:
            if v and v != key and v not in existing:
                existing.append(v)
        for v in vals:
            if not v or v == key:
                continue
            rev = index.setdefault(v, [])
            if key not in rev:
                rev.append(key)
    return index


_SYNONYM_INDEX: dict[str, list[str]] = _build_synonym_index()


def expand_query_simple(query_tokens: list[str]) -> list[str]:
    """
    Conservative synonym expansion for non-compound queries.
    Only expands single tokens and bigrams. Does NOT flatten phrases into tokens.
    """
    expanded: list[str] = list(query_tokens)

    def _add(token: str) -> None:
        if token and token not in expanded:
            expanded.append(token)

    # Single-token synonyms
    for tok in query_tokens:
        for syn in _SYNONYM_INDEX.get(tok, []):
            _add(syn)

    # Bigram synonyms
    for i in range(len(query_tokens) - 1):
        bigram = f"{query_tokens[i]} {query_tokens[i+1]}"
        for syn in _SYNONYM_INDEX.get(bigram, []):
            _add(syn)

    return expanded
