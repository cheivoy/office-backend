from fastapi import APIRouter, HTTPException, UploadFile, File
from models.schemas import Person
from services import people_svc

router = APIRouter()


@router.get("/people")
def list_people():
    return people_svc.get_all()


@router.post("/people")
def add_or_update(person: Person):
    return people_svc.upsert(person)


@router.delete("/people/{person_id}")
def remove(person_id: int):
    if not people_svc.delete(person_id):
        raise HTTPException(404, "Person not found")
    return {"deleted": person_id}


@router.post("/people/import")
async def import_people(file: UploadFile = File(...)):
    data = await file.read()
    try:
        merged = people_svc.import_from_excel(data)
    except Exception as e:
        raise HTTPException(400, f"Import failed: {e}")
    return {"imported": len(merged), "people": merged}
