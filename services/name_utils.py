"""
Fuzzy name matching for Chinese/English/mixed names.
Used by verify_svc, excel_svc, and report_svc.
"""
import re
import unicodedata


def _normalize(s: str) -> str:
    if not s:
        return ""
    s = str(s)
    s = unicodedata.normalize("NFKC", s)
    # keep only CJK, latin letters, spaces
    s = re.sub(r"[（(（）)）\-_\.\,，。]", " ", s)
    return s.lower().strip()


def _tokens(s: str) -> list[str]:
    n = _normalize(s)
    return [t for t in n.split() if len(t) >= 2]


def name_match(cell_name: str, emp_en: str, emp_cn: str = "") -> bool:
    """
    Return True if cell_name likely refers to the same person.
    Strategy:
    1. Exact normalized match on English name
    2. All tokens of English name found in cell
    3. Chinese name substring
    """
    if not cell_name:
        return False
    cell = _normalize(cell_name)

    # exact English
    if emp_en and _normalize(emp_en) == cell:
        return True

    # all English tokens present
    if emp_en:
        toks = _tokens(emp_en)
        if toks and all(t in cell for t in toks):
            return True
        # at least last name + first name (first two tokens)
        if len(toks) >= 2 and toks[0] in cell and toks[1] in cell:
            return True

    # Chinese substring
    if emp_cn and emp_cn.strip() and emp_cn.strip() in cell_name:
        return True

    return False


def parse_date(val) -> str | None:
    """Convert Excel serial, datetime, or string to YYYY-MM-DD."""
    if val is None:
        return None
    import datetime
    if isinstance(val, datetime.datetime):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, datetime.date):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, (int, float)):
        # Excel serial date
        try:
            base = datetime.datetime(1899, 12, 30)
            d = base + datetime.timedelta(days=int(val))
            return d.strftime("%Y-%m-%d")
        except Exception:
            return None
    if isinstance(val, str):
        val = val.strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"):
            try:
                return datetime.datetime.strptime(val, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        # partial like "0506" -> best effort
        return val
    return str(val)


def parse_mmdd(s: str) -> list[str]:
    """Parse '0504 0514' or '0504, 0514' into ['0504','0514']."""
    if not s:
        return []
    return re.findall(r"\d{4}", str(s))


def parse_time_range(s: str) -> tuple[str, str] | None:
    """Parse '18:00 - 19:00' or '18:00-19:00' into ('18:00','19:00')."""
    if not s:
        return None
    m = re.search(r"(\d{1,2}:\d{2})\s*[-~–]\s*(\d{1,2}:\d{2})", str(s))
    if m:
        return m.group(1).zfill(5), m.group(2).zfill(5)
    return None


def hours_from_range(start: str, end: str) -> float:
    """Calculate hours between HH:MM strings, crossing midnight allowed."""
    sh, sm = map(int, start.split(":"))
    eh, em = map(int, end.split(":"))
    mins = (eh * 60 + em) - (sh * 60 + sm)
    if mins < 0:
        mins += 1440
    return round(mins / 60, 2)
