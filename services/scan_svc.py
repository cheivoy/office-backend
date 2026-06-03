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


def scan_and_classify() -> dict:
    """
    Scan Inbox/, match each file to an employee, move to
    Departments/<proj>/<unit>/<pm>/<emp_en>/<file>.
    Returns kanban data: {emp_id: {file_type: bool}}.
    """
    results = {"moved": [], "unmatched": [], "kanban": {}}

    inbox_files = list(INBOX_DIR.iterdir())
    people = get_all()

    for fpath in inbox_files:
        if not fpath.is_file():
            continue
        matched = _match_person(fpath.name, people)
        if not matched:
            results["unmatched"].append(fpath.name)
            continue

        dest_dir = _emp_dir(matched)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / fpath.name
        # avoid overwrite: append suffix if exists
        if dest.exists():
            dest = dest_dir / (fpath.stem + "_dup" + fpath.suffix)
        shutil.move(str(fpath), str(dest))

        ftype = _detect_type(fpath.name)
        eid = matched["id"]
        if eid not in results["kanban"]:
            results["kanban"][eid] = {}
        results["kanban"][eid][ftype] = True
        results["moved"].append({
            "file": fpath.name,
            "emp": matched["en"],
            "type": ftype,
            "dest": str(dest.relative_to(DEPT_DIR)),
        })

    # Build full kanban with all employees
    full_kanban = _build_full_kanban(people, results["kanban"])
    results["kanban"] = full_kanban
    return results


def _match_person(filename: str, people: list[dict]) -> dict | None:
    fn = filename.lower().replace("_", " ").replace("-", " ")
    best = None
    best_score = 0
    for p in people:
        score = 0
        en = p.get("en", "").lower()
        cn = p.get("cn", "")
        # full English name
        if en and en in fn:
            score = len(en)
        # parts of English name
        elif en:
            parts = [x for x in en.split() if len(x) > 2]
            matched_parts = sum(1 for x in parts if x in fn)
            if matched_parts == len(parts) and len(parts) > 0:
                score = len(en) * 0.8
            elif matched_parts > 0:
                score = matched_parts * 3
        # Chinese name
        if cn and cn in filename:
            score = max(score, len(cn) * 2)
        if score > best_score:
            best_score = score
            best = p
    return best if best_score >= 3 else None


def _emp_dir(person: dict) -> Path:
    proj = person.get("proj", "unknown")
    unit = person.get("unit", "") or "_no_unit"
    pm   = person.get("pm", "")  or "_no_pm"
    en   = person.get("en", "unknown").replace(" ", "_")
    return DEPT_DIR / proj / unit / pm / en


def _build_full_kanban(people: list[dict], moved_map: dict) -> list[dict]:
    from pathlib import Path
    kanban = []
    for p in people:
        eid = p["id"]
        emp_dir = _emp_dir(p)
        status = {}
        if emp_dir.exists():
            for fpath in emp_dir.iterdir():
                if fpath.is_file():
                    ftype = _detect_type(fpath.name)
                    if ftype != "other":
                        status[ftype] = True
        kanban.append({
            "id":         eid,
            "cn":         p.get("cn", ""),
            "en":         p.get("en", ""),
            "proj":       p.get("proj", ""),
            "unit":       p.get("unit", ""),
            "pm":         p.get("pm", ""),
            "status":     status,
            "uploadDate": _latest_date(emp_dir),
        })
    return kanban


def _latest_date(emp_dir: Path) -> str:
    import datetime
    if not emp_dir.exists():
        return ""
    dates = []
    for f in emp_dir.iterdir():
        if f.is_file():
            dates.append(f.stat().st_mtime)
    if not dates:
        return ""
    ts = max(dates)
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def get_employee_files(emp_en: str) -> list[dict]:
    person = find_by_name(emp_en)
    if not person:
        return []
    emp_dir = _emp_dir(person)
    if not emp_dir.exists():
        return []
    files = []
    for f in sorted(emp_dir.iterdir()):
        if f.is_file():
            ext = f.suffix.lower().lstrip(".")
            files.append({
                "name": f.name,
                "type": ext if ext in ("pdf", "xlsx", "eml") else "other",
                "size": f.stat().st_size,
                "ftype": _detect_type(f.name),
            })
    return files
