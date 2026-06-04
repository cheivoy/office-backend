from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from models.schemas import Person
from services import people_svc

router = APIRouter()


@router.get("/people")
def list_people(period: str = ""):
    """Return people list. If period given, return period-specific roster."""
    return people_svc.get_all(period=period)


@router.post("/people")
def add_or_update(person: Person, period: str = ""):
    """新增/更新員工。帶 ?period=2026-P05 時操作該月份名單。"""
    return people_svc.upsert(person, period=period)


@router.delete("/people/{person_id}")
def remove(person_id: int, period: str = ""):
    """刪除員工。帶 ?period=2026-P05 時只從該月份名單刪除。"""
    if not people_svc.delete(person_id, period=period):
        raise HTTPException(404, "Person not found")
    return {"deleted": person_id, "period": period or None}


@router.post("/people/import")
async def import_people(
    file: UploadFile = File(...),
    period: str = Form(""),
):
    """
    Import people from Excel.
    period 有值時：完全覆蓋該月份專屬名單（不污染全域）。
    period 為空時：合併進全域名單。
    """
    data = await file.read()
    try:
        merged = people_svc.import_from_excel(data, period=period)
    except Exception as e:
        raise HTTPException(400, f"Import failed: {e}")
    return {"imported": len(merged), "people": merged, "period": period or None}


@router.get("/people/roster-periods")
def roster_periods():
    """Return list of periods that have dedicated roster snapshots."""
    return {"periods": people_svc.get_roster_periods()}


@router.delete("/people/roster/{period}")
def remove_roster(period: str):
    """整份刪除某月份名單（之後該月份回退使用全域名單）。"""
    if not people_svc.delete_roster(period):
        raise HTTPException(404, f"Roster for '{period}' not found")
    return {"deleted_roster": period}
