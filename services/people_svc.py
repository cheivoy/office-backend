import json
from pathlib import Path
from openpyxl import load_workbook
from config import PEOPLE_CSV
from models.schemas import Person

def _load() -> list[dict]:
    if PEOPLE_CSV.exists():
        return json.loads(PEOPLE_CSV.read_text(encoding="utf-8"))
    return []

def _save(people: list[dict]):
    PEOPLE_CSV.write_text(json.dumps(people, ensure_ascii=False, indent=2), encoding="utf-8")

def get_all() -> list[dict]:
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

def import_from_excel(file_bytes: bytes) -> list[dict]:
    """
    Read Excel with columns: 專案 / 單位 / PM / 中文姓名 / 英文姓名
    Merge into existing list (upsert by English name).
    """
    from io import BytesIO
    wb = load_workbook(BytesIO(file_bytes), read_only=True)
    ws = wb.active
    people = _load()
    existing = {p["en"]: p for p in people}
    max_id = max((p["id"] for p in people), default=0)

    header_skipped = False
    for row in ws.iter_rows(values_only=True):
        if not header_skipped:
            header_skipped = True
            continue
        if not row or not row[4]:
            continue
        proj, unit, pm, cn, en = (str(v).strip() if v else "" for v in row[:5])
        if en in existing:
            existing[en].update({"proj": proj, "unit": unit, "pm": pm, "cn": cn})
        else:
            max_id += 1
            existing[en] = {"id": max_id, "proj": proj, "unit": unit, "pm": pm, "cn": cn, "en": en}

    merged = list(existing.values())
    _save(merged)
    return merged

def find_by_name(name: str) -> dict | None:
    """Match by Chinese name, English name, or partial English name."""
    name_l = name.lower().replace("_", " ").replace("-", " ")
    for p in _load():
        if name_l in (p.get("cn", "") + " " + p.get("en", "")).lower():
            return p
        # also try last-name only or first-name only
        parts = p.get("en", "").lower().split()
        if any(part in name_l for part in parts if len(part) > 2):
            return p
    return None
