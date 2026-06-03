from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from config import INBOX_DIR
from services.scan_svc import scan_and_classify, get_employee_files
import shutil

router = APIRouter()

@router.post("/scan-and-classify")
async def scan(period: str = Form("")):
    result = scan_and_classify(period=period)
    return result

@router.post("/import-files")
async def import_files(files: list[UploadFile] = File(...)):
    saved = []
    for f in files:
        dest = INBOX_DIR / f.filename
        with dest.open("wb") as out:
            shutil.copyfileobj(f.file, out)
        saved.append(f.filename)
    return {"saved": saved, "count": len(saved)}

@router.get("/employee-files/{emp_en}")
def employee_files(emp_en: str, period: str = ""):
    files = get_employee_files(emp_en, period=period)
    return {"files": files}
