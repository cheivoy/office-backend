from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from config import INBOX_DIR
from services.scan_svc import (
    scan_and_classify, get_employee_files,
    get_inbox_files, assign_manual
)
from services.people_svc import get_all
import shutil

router = APIRouter()


@router.post("/scan-and-classify")
async def scan(period: str = Form("")):
    result = scan_and_classify(period=period)
    return result


@router.post("/import-files")
async def import_files(files: list[UploadFile] = File(...)):
    """
    Save files to Inbox, preserving subfolder structure from browser upload.
    f.filename may include relative path like 'WIPRO P05/file.xlsx'.
    Parent folders are created automatically. Duplicates are skipped.
    """
    from pathlib import PurePosixPath
    from services.scan_svc import _safe_dest
    saved, skipped = [], []
    for f in files:
        # Parse relative path safely (no absolute path escape)
        rel = PurePosixPath(f.filename)
        dest = INBOX_DIR.joinpath(*rel.parts)
        file_bytes = await f.read()

        # Skip exact duplicate (same path + same size)
        if dest.exists() and dest.stat().st_size == len(file_bytes):
            skipped.append(f.filename)
            continue

        # Create parent dirs (preserves folder structure in Inbox)
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Avoid overwrite if different content
        if dest.exists():
            dest = _safe_dest(dest)

        dest.write_bytes(file_bytes)
        saved.append(str(dest.relative_to(INBOX_DIR)))

    return {"saved": saved, "skipped": skipped, "count": len(saved)}


@router.get("/inbox-files")
def inbox_files():
    """List all files currently in Inbox waiting to be scanned."""
    return {"files": get_inbox_files()}


@router.post("/assign-manual")
async def manual_assign(
    inbox_path: str = Form(...),
    emp_name:   str = Form(...),
    period:     str = Form(""),
):
    """Manually assign an unmatched Inbox file to an employee."""
    try:
        result = assign_manual(inbox_path, emp_name, period)
        return result
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(400, str(e))


@router.get("/employee-files/{emp_en}")
def employee_files(emp_en: str, period: str = ""):
    return {"files": get_employee_files(emp_en, period=period)}


@router.get("/periods")
def get_periods():
    """Return all year-period folders found (e.g. 2026-P05)."""
    from config import DEPT_DIR
    periods = set()
    if DEPT_DIR.exists():
        for p in DEPT_DIR.rglob("*"):
            if p.is_dir() and "-P" in p.name and p.name[:2].isdigit():
                periods.add(p.name)
    return {"periods": sorted(periods)}


@router.get("/people")
def list_people_for_assign():
    """Quick list for manual assign dropdown."""
    return [{"en": p["en"], "cn": p.get("cn","")} for p in get_all()]