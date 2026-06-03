from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from config import INBOX_DIR
from services.scan_svc import scan_and_classify, get_employee_files
import shutil

router = APIRouter()


@router.post("/scan-and-classify")
def scan():
    result = scan_and_classify()
    return result


@router.post("/import-files")
async def import_files(files: list[UploadFile] = File(...)):
    """Save uploaded files to Inbox/ for later scanning."""
    saved = []
    for f in files:
        dest = INBOX_DIR / f.filename
        with dest.open("wb") as out:
            shutil.copyfileobj(f.file, out)
        saved.append(f.filename)
    return {"saved": saved, "count": len(saved)}


@router.get("/employee-files/{emp_en}")
def employee_files(emp_en: str):
    files = get_employee_files(emp_en)
    return {"files": files}
