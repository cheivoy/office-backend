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


def scan_and_classify(period: str = "") -> dict:
    """
    Scan Inbox/, match files to employees, move to:
      Departments/<proj>/<unit>/<pm>/<emp_en>/<period>/   if period given
      Departments/<proj>/<unit>/<pm>/<emp_en>/             otherwise
    period: e.g. "2026-P05"
    """
    results = {"moved": [], "unmatched": [], "kanban": []}
    people  = get_all()

    for fpath in list(INBOX_DIR.iterdir()):
        if not fpath.is_file():
            continue
        matched = _match_person(fpath.name, people)
        if not matched:
            results["unmatched"].append(fpath.name)
            continue

        base_dir = _emp_dir(matched)
        dest_dir = base_dir / period if period else base_dir
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest = dest_dir / fpath.name
        if dest.exists():
            dest = dest_dir / (fpath.stem + "_dup" + fpath.suffix)
        shutil.move(str(fpath), str(dest))

        results["moved"].append({
            "file":   fpath.name,
            "emp":    matched["en"],
            "type":   _detect_type(fpath.name),
            "period": period,
            "dest":   str(dest.relative_to(DEPT_DIR)),
        })

    results["kanban"] = _build_full_kanban(people)
    return results


def _match_person(filename: str, people: list[dict]) -> dict | None:
    fn = filename.lower().replace("_", " ").replace("-", " ")
    best, best_score = None, 0
    for p in people:
        score = 0
        en = p.get("en", "").lower()
        cn = p.get("cn", "")
        if en and en in fn:
            score = len(en)
        elif en:
            parts = [x for x in en.split() if len(x) > 2]
            matched = sum(1 for x in parts if x in fn)
            if matched == len(parts) and len(parts) > 0:
                score = len(en) * 0.8
            elif matched > 0:
                score = matched * 3
        if cn and cn in filename:
            score = max(score, len(cn) * 2)
        if score > best_score:
            best_score = score
            best = p
    return best if best_score >= 3 else None


def _emp_dir(person: dict) -> Path:
    proj = person.get("proj", "unknown")
    unit = person.get("unit", "") or "_no_unit"
    pm   = person.get("pm",   "") or "_no_pm"
    en   = person.get("en",   "unknown").replace(" ", "_")
    return DEPT_DIR / proj / unit / pm / en


def _build_full_kanban(people: list[dict]) -> list[dict]:
    import datetime
    kanban = []
    for p in people:
        emp_dir = _emp_dir(p)
        status  = {}
        periods = set()
        if emp_dir.exists():
            for item in emp_dir.rglob("*"):
                if item.is_file():
                    ftype = _detect_type(item.name)
                    if ftype != "other":
                        status[ftype] = True
                    # collect period folders (2026-P05 etc.)
                    rel = item.relative_to(emp_dir)
                    parts = rel.parts
                    if len(parts) >= 2:
                        periods.add(parts[0])
        kanban.append({
            "id":         p["id"],
            "cn":         p.get("cn", ""),
            "en":         p.get("en", ""),
            "proj":       p.get("proj", ""),
            "unit":       p.get("unit", ""),
            "pm":         p.get("pm", ""),
            "status":     status,
            "periods":    sorted(periods),
            "uploadDate": _latest_date(emp_dir),
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
    files = []
    search_dir = emp_dir / period if (period and (emp_dir/period).exists()) else emp_dir
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
