import re
from typing import List, Dict

PRICE_RE = re.compile(r"\d+[\.,]?\d*")


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
        return float(m.group().replace(',', ''))
    except:
        return None


def expand_and_normalize_items(items: List[Dict]) -> List[Dict]:
    out = []
    for it in items:
        # If price_display contains slashes and item_name contains slashes and counts match -> split
        name = it.get("item_name")
        pdisp = it.get("price_display") or ""

        # Clean tokens
        name_tokens = [t.strip() for t in re.split(r"[\/,]", name) if t.strip()] if name else [name]
        price_tokens = [t.strip() for t in re.split(r"[\/,]", pdisp) if t.strip()]

        if len(name_tokens) > 1 and len(price_tokens) == len(name_tokens):
            # split into separate items
            for nt, pt in zip(name_tokens, price_tokens):
                new = it.copy()
                # Try to preserve heading if exists: append parent category if not present in name
                new["item_name"] = nt
                new["price_display"] = pt
                new["price"] = _parse_numeric(pt)
                out.append(new)
            continue

        # if base item and price_display has multiple prices but no multiple names -> leave as is
        # attempt to parse single price
        it["price"] = _parse_numeric(pdisp) if it.get("price") is None else it.get("price")
        out.append(it)
    return out
