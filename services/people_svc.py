import json
from pathlib import Path
from openpyxl import load_workbook
from config import PEOPLE_CSV
from models.schemas import Person

# ── Storage helpers ────────────────────────────────────────────────────────────

def _load() -> list[dict]:
    if PEOPLE_CSV.exists():
        return json.loads(PEOPLE_CSV.read_text(encoding="utf-8"))
    return []

def _save(people: list[dict]):
    PEOPLE_CSV.write_text(json.dumps(people, ensure_ascii=False, indent=2), encoding="utf-8")

# ── Period roster storage ──────────────────────────────────────────────────────
# Each period has its OWN snapshot of the roster, stored in data/roster_<period>.json
# This allows different headcounts per period (joins/departures).

def _roster_path(period: str) -> Path:
    from config import BASE_DIR
    return BASE_DIR / "data" / f"roster_{period}.json"

def _load_roster(period: str) -> list[dict] | None:
    """Load period-specific roster. Returns None if not set (fall back to global)."""
    p = _roster_path(period)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None

def _save_roster(period: str, people: list[dict]):
    _roster_path(period).write_text(
        json.dumps(people, ensure_ascii=False, indent=2), encoding="utf-8"
    )

def get_roster_periods() -> list[str]:
    """Return list of periods that have a saved roster snapshot."""
    from config import BASE_DIR
    data_dir = BASE_DIR / "data"
    periods = []
    for f in sorted(data_dir.glob("roster_*.json")):
        period = f.stem.replace("roster_", "")
        periods.append(period)
    return periods

# ── CRUD (global people list) ──────────────────────────────────────────────────

def get_all(period: str = "") -> list[dict]:
    """Return people for a given period (falls back to global list)."""
    if period:
        roster = _load_roster(period)
        if roster is not None:
            return roster
    return _load()

def upsert(person: Person) -> dict:
    people = _load()
    if person.id is not None:
        for i, p in enumerate(people):
            if p["id"] == person.id:
                people[i] = person.model_dump()
                _save(people)
                return people[i]
    new_id = max((p["id"] for p in people), default=0) + 1
    data = person.model_dump()
    data["id"] = new_id
    people.append(data)
    _save(people)
    return data

def delete(person_id: int) -> bool:
    people = _load()
    new = [p for p in people if p["id"] != person_id]
    if len(new) == len(people):
        return False
    _save(new)
    return True

def import_from_excel(file_bytes: bytes, period: str = "") -> list[dict]:
    """
    Read Excel with columns: 專案 / 單位 / PM / 中文姓名 / 英文姓名

    If period is given, the imported list is saved as a period-specific roster
    snapshot (does NOT touch the global people list).
    If no period, merges into the global list (upsert by English name).
    """
    from io import BytesIO
    wb = load_workbook(BytesIO(file_bytes), read_only=True)
    ws = wb.active

    header_skipped = False
    imported = []
    for row in ws.iter_rows(values_only=True):
        if not header_skipped:
            header_skipped = True
            continue
        if not row or not row[4]:
            continue
        proj, unit, pm, cn, en = (str(v).strip() if v else "" for v in row[:5])
        imported.append({"proj": proj, "unit": unit, "pm": pm, "cn": cn, "en": en})

    if period:
        # Build a clean period roster with stable IDs
        # Match by en name against global list; assign new IDs for newcomers
        global_people = _load()
        existing_by_en = {p["en"]: p for p in global_people}
        max_id = max((p["id"] for p in global_people), default=0)

        roster = []
        for item in imported:
            if item["en"] in existing_by_en:
                base = dict(existing_by_en[item["en"]])
                base.update({k: item[k] for k in ("proj", "unit", "pm", "cn") if item[k]})
                roster.append(base)
            else:
                # New person (not in global list yet) — add to global too
                max_id += 1
                new_person = {"id": max_id, **item}
                global_people.append(new_person)
                existing_by_en[item["en"]] = new_person
                roster.append(new_person)

        _save(global_people)     # update global with any new people
        _save_roster(period, roster)
        return roster
    else:
        # Legacy: merge into global
        people = _load()
        existing = {p["en"]: p for p in people}
        max_id = max((p["id"] for p in people), default=0)
        for item in imported:
            if item["en"] in existing:
                existing[item["en"]].update({k: item[k] for k in ("proj", "unit", "pm", "cn") if item[k]})
            else:
                max_id += 1
                existing[item["en"]] = {"id": max_id, **item}
        merged = list(existing.values())
        _save(merged)
        return merged

def find_by_name(name: str, period: str = "") -> dict | None:
    """Match by Chinese name, English name, or partial English name."""
    people = get_all(period)
    name_l = name.lower().replace("_", " ").replace("-", " ")
    for p in people:
        if name_l in (p.get("cn", "") + " " + p.get("en", "")).lower():
            return p
        parts = p.get("en", "").lower().split()
        if any(part in name_l for part in parts if len(part) > 2):
            return p
    return None
