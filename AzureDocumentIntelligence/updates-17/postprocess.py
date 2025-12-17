import re
from typing import List, Dict

PRICE_RE = re.compile(r"\d+[\.,]?\d*")

PRICE_FIELDS = [
    "price",
    "small_price",
    "medium_price",
    "large_price",
    "half_plate_price",
    "full_plate_price",
]


def _parse_numeric(s: str):
    if s is None:
        return None
    s = str(s).strip()
    # remove currency symbols and commas
    s = re.sub(r"[\$₹€,]", "", s)
    # if range like 250-350, take lower bound
    if "-" in s:
        s = s.split("-")[0]
    m = PRICE_RE.search(s)
    if not m:
        return None
    try:
        return float(m.group().replace(",", ""))
    except:
        return None


def expand_and_normalize_items(items: List[Dict]) -> List[Dict]:
    out = []

    for it in items:
        it = dict(it)  # defensive copy

        # ---------------------------------------------
        # 1️⃣ EXISTING SLASH-BASED SPLIT LOGIC (UNCHANGED)
        # ---------------------------------------------
        name = it.get("item_name")
        pdisp = it.get("price_display") or ""

        name_tokens = (
            [t.strip() for t in re.split(r"[\/,]", name) if t.strip()]
            if name else [name]
        )
        price_tokens = [t.strip() for t in re.split(r"[\/,]", pdisp) if t.strip()]

        if len(name_tokens) > 1 and len(price_tokens) == len(name_tokens):
            for nt, pt in zip(name_tokens, price_tokens):
                new = it.copy()
                new["item_name"] = nt
                new["price_display"] = pt
                new["price"] = _parse_numeric(pt)
                out.append(_normalize_price_fields(new))
            continue

        # ---------------------------------------------
        # 2️⃣ SINGLE PRICE FROM price_display (UNCHANGED)
        # ---------------------------------------------
        if it.get("price") is None:
            it["price"] = _parse_numeric(pdisp)

        # ---------------------------------------------
        # 3️⃣ 🔥 NEW: FLATTEN VARIANT PRICE → price
        # ---------------------------------------------
        it = _normalize_price_fields(it)

        out.append(it)

    return out


def _normalize_price_fields(item: Dict) -> Dict:
    """
    Move any variant price (small/large/etc.) into `price`
    and remove other price columns.
    """

    # If price already exists, trust it
    if item.get("price") is not None:
        pass
    else:
        # Pick first available variant price
        for field in PRICE_FIELDS:
            if item.get(field) is not None:
                item["price"] = item[field]
                break

    # Remove all variant fields except `price`
    for field in PRICE_FIELDS:
        if field != "price":
            item.pop(field, None)

    return item
