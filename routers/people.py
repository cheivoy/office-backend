from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from models.schemas import Person
from services import people_svc

router = APIRouter()


@router.get("/people")
def list_people(period: str = ""):
    """Return people list. If period given, return period-specific roster."""
    return people_svc.get_all(period=period)


@router.post("/people")
def add_or_update(person: Person):
    return people_svc.upsert(person)


@router.delete("/people/{person_id}")
def remove(person_id: int):
    if not people_svc.delete(person_id):
        raise HTTPException(404, "Person not found")
    return {"deleted": person_id}


@router.post("/people/import")
async def import_people(
    file: UploadFile = File(...),
    period: str = Form(""),
):
    """
    Import people from Excel.
    If period is provided, creates a period-specific roster snapshot.
    If not, merges into the global people list.
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
