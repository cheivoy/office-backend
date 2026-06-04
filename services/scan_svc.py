import shutil
from pathlib import Path
from config import INBOX_DIR, DEPT_DIR, FILE_TYPE_KEYWORDS
from services.people_svc import get_all, find_by_name


def _detect_type(filename: str) -> str:
    fn = filename.lower()
    for ftype, keywords in FILE_TYPE_KEYWORDS.items():
        if any(kw.lower() in fn for kw in keywords):
            return ftype
    return "other"


def _safe_dest(dest: Path) -> Path:
    """Return a non-conflicting path by appending _2, _3... if needed."""
    if not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    counter = 2
    while True:
        candidate = dest.parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _normalize(s: str) -> str:
    """Lowercase, strip accents/spaces/separators for flexible matching."""
    import unicodedata
    s = s.lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    for ch in ("_", "-", ".", "(", ")", " ", "\t"):
        s = s.replace(ch, "")
    return s


def _match_by_name(filename: str, people: list[dict]) -> dict | None:
    """
    Match employee by name in filename.

    Strategy:
    1. Chinese full name (>= 2 chars) as exact substring → highest priority
    2. English full name (all parts concatenated, no spaces) as substring
       e.g. "CherryWong" matches "Cherry Wong"
    3. English full name with spaces/separators present
    4. All name parts must match (both first AND last), single-part names need
       >= 4 chars and exact token match to avoid false positives.
    5. Minimum score threshold; ties → None (ambiguous).
    """
    fn_raw = filename          # preserve for Chinese
    fn_norm = _normalize(filename)   # normalised (no separators, lowercase)
    fn_lower = filename.lower().replace("_", " ").replace("-", " ").replace(".", " ").replace("(", " ").replace(")", " ")

    candidates = []

    for p in people:
        score = 0
        en = p.get("en", "").strip()
        cn = p.get("cn", "").strip()

        # ── 1. Chinese full-name exact substring ──────────────────────────────
        if cn and len(cn) >= 2:
            if cn in fn_raw:
                score = len(cn) * 10

        # ── 2 & 3. English name matching ──────────────────────────────────────
        if en and score == 0:
            en_lower = en.lower()
            en_norm  = _normalize(en)           # e.g. "cherrywong"
            fn_parts = fn_lower.split()

            # 2a. Full name concatenated (no spaces) — handles "CherryWong"
            if en_norm and en_norm in fn_norm:
                score = len(en_norm) * 6

            # 2b. Full name with spaces in filename
            elif en_lower in fn_lower:
                score = len(en_lower) * 5

            else:
                # 3. All individual name parts must appear
                name_parts = [x for x in en_lower.split() if len(x) >= 2]
                if len(name_parts) >= 2:
                    matched_parts = []
                    for part in name_parts:
                        part_norm = _normalize(part)
                        # exact token match (with separators)
                        if part in fn_parts:
                            matched_parts.append(part)
                        # substring match in normalised string (handles CamelCase concat)
                        elif len(part_norm) >= 3 and part_norm in fn_norm:
                            matched_parts.append(part)
                        # substring match for longer parts in original
                        elif len(part) >= 4 and part in fn_lower:
                            matched_parts.append(part)
                    if len(matched_parts) == len(name_parts):
                        score = len(en_lower) * 3
                    elif len(matched_parts) >= 2:
                        score = len(en_lower) * 2

                elif len(name_parts) == 1 and len(name_parts[0]) >= 4:
                    if name_parts[0] in fn_parts:
                        score = len(name_parts[0]) * 3

        if score > 0:
            candidates.append((score, p))

    if not candidates:
        return None

    candidates.sort(key=lambda x: -x[0])
    best_score = candidates[0][0]

    top = [p for s, p in candidates if s == best_score]
    if len(top) > 1:
        return None   # ambiguous

    return top[0] if best_score >= 6 else None


def _match_by_folder(folder_name: str, people: list[dict]) -> dict | None:
    return _match_by_name(folder_name, people)


def scan_and_classify(period: str = "") -> dict:
    """
    Scan Inbox/, match files to employees.
    Strategy per file:
      1. Match by filename (name in filename)
      2. Match by parent folder name (if file came from a subfolder)
      3. Unmatched → needs manual assignment
    No overwrite: uses _safe_dest for duplicate filenames.
    """
    results = {"moved": [], "unmatched": [], "kanban": []}
    people  = get_all(period=period)  # use period-specific roster if available

    for fpath in list(INBOX_DIR.rglob("*")):
        if not fpath.is_file():
            continue

        matched = _match_by_name(fpath.name, people)

        # Fallback: try folder name
        if not matched:
            rel = fpath.relative_to(INBOX_DIR)
            if len(rel.parts) > 1:
                folder = rel.parts[0]
                matched = _match_by_folder(folder, people)

        if not matched:
            results["unmatched"].append({
                "file": str(fpath.relative_to(INBOX_DIR)),
                "inbox_path": str(fpath),
            })
            continue

        base_dir = _emp_dir(matched)
        dest_dir = base_dir / period if period else base_dir
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest = _safe_dest(dest_dir / fpath.name)
        shutil.move(str(fpath), str(dest))

        results["moved"].append({
            "file":      fpath.name,
            "emp_en":    matched["en"],
            "emp_cn":    matched.get("cn",""),
            "proj":      matched.get("proj",""),
            "unit":      matched.get("unit",""),
            "type":      _detect_type(fpath.name),
            "period":    period,
            "dest":      str(dest.relative_to(DEPT_DIR)),
            "method":    "name" if _match_by_name(fpath.name, people) else "folder",
        })

    # Clean up empty Inbox subfolders
    for d in sorted(INBOX_DIR.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()

    results["kanban"] = _build_full_kanban(people, active_period=period)
    return results


def assign_manual(inbox_path: str, emp_en: str, period: str = "") -> dict:
    """Manually assign an unmatched file to an employee."""
    person = find_by_name(emp_en)
    if not person:
        raise ValueError(f"Employee '{emp_en}' not found")

    src = Path(inbox_path)
    if not src.exists():
        raise FileNotFoundError(f"File not found: {inbox_path}")

    base_dir = _emp_dir(person)
    dest_dir = base_dir / period if period else base_dir
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = _safe_dest(dest_dir / src.name)
    shutil.move(str(src), str(dest))

    return {
        "file":   src.name,
        "emp":    person["en"],
        "type":   _detect_type(src.name),
        "dest":   str(dest.relative_to(DEPT_DIR)),
    }


def _emp_dir(person: dict) -> Path:
    proj = person.get("proj", "unknown")
    unit = person.get("unit", "") or "_no_unit"
    pm   = person.get("pm",   "") or "_no_pm"
    en   = person.get("en",   "unknown").replace(" ", "_")
    return DEPT_DIR / proj / unit / pm / en


def _build_full_kanban(people: list[dict], active_period: str = "") -> list[dict]:
    import datetime
    kanban = []
    for p in people:
        emp_dir = _emp_dir(p)
        status, periods = {}, set()
        if emp_dir.exists():
            for item in emp_dir.rglob("*"):
                if item.is_file():
                    ftype = _detect_type(item.name)
                    if ftype != "other":
                        rel = item.relative_to(emp_dir)
                        period_folder = rel.parts[0] if len(rel.parts) >= 2 else ""
                        if period_folder:
                            # Track status per period
                            if period_folder not in status:
                                status[period_folder] = {}
                            status[period_folder][ftype] = "ok"
                        else:
                            # No period subfolder → top-level
                            if "" not in status:
                                status[""] = {}
                            status[""][ftype] = "ok"
                    rel = item.relative_to(emp_dir)
                    if len(rel.parts) >= 2:
                        periods.add(rel.parts[0])
        kanban.append({
            "id":            p["id"],
            "cn":            p.get("cn", ""),
            "en":            p.get("en", ""),
            "proj":          p.get("proj", ""),
            "unit":          p.get("unit", ""),
            "pm":            p.get("pm", ""),
            "status":        status.get("", {}),  # top-level for backward compat
            "periodStatus":  status,              # per-period breakdown
            "periods":       sorted(periods),
            "uploadDate":    _latest_date(emp_dir),
        })
    return kanban


def _latest_date(emp_dir: Path) -> str:
    import datetime
    if not emp_dir.exists():
        return ""
    dates = [f.stat().st_mtime for f in emp_dir.rglob("*") if f.is_file()]
    if not dates:
        return ""
    return datetime.datetime.fromtimestamp(max(dates)).strftime("%Y-%m-%d")


def get_employee_files(emp_en: str, period: str = "") -> list[dict]:
    person = find_by_name(emp_en)
    if not person:
        return []
    emp_dir = _emp_dir(person)
    if not emp_dir.exists():
        return []
    search_dir = emp_dir / period if (period and (emp_dir/period).exists()) else emp_dir
    files = []
    for f in sorted(search_dir.rglob("*")):
        if f.is_file():
            ext = f.suffix.lower().lstrip(".")
            rel = f.relative_to(emp_dir)
            files.append({
                "name":    f.name,
                "path":    str(rel),
                "type":    ext if ext in ("pdf", "xlsx", "eml") else "other",
                "ftype":   _detect_type(f.name),
                "period":  rel.parts[0] if len(rel.parts) > 1 else "",
                "size":    f.stat().st_size,
            })
    return files


def get_inbox_files() -> list[dict]:
    """Return all files currently in Inbox (unscanned)."""
    files = []
    for f in sorted(INBOX_DIR.rglob("*")):
        if f.is_file():
            rel = f.relative_to(INBOX_DIR)
            files.append({
                "name":        f.name,
                "inbox_path":  str(f),
                "folder":      rel.parts[0] if len(rel.parts) > 1 else "",
                "size":        f.stat().st_size,
            })
    return files
