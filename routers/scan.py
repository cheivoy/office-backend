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
    Save files to Inbox.
    Returns duplicates list so frontend can ask user for confirmation.
    Supports both single file and folder (webkitdirectory) uploads.
    """
    from pathlib import PurePosixPath
    from services.scan_svc import _safe_dest

    saved, skipped, duplicates = [], [], []

    for f in files:
        # webkitRelativePath is sent as the filename for folder uploads;
        # for single-file uploads it's just the bare filename.
        rel  = PurePosixPath(f.filename)
        dest = INBOX_DIR.joinpath(*rel.parts)
        file_bytes = await f.read()

        if dest.exists():
            duplicates.append({
                "filename":   f.filename,
                "inbox_path": str(dest),
                "size_match": dest.stat().st_size == len(file_bytes),
            })
            skipped.append(f.filename)
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(file_bytes)
        saved.append(str(dest.relative_to(INBOX_DIR)))

    return {
        "saved":      saved,
        "skipped":    skipped,
        "duplicates": duplicates,
        "count":      len(saved),
    }


@router.post("/import-files-force")
async def import_files_force(files: list[UploadFile] = File(...)):
    """Force import, overwriting existing files."""
    from pathlib import PurePosixPath
    saved = []
    for f in files:
        rel  = PurePosixPath(f.filename)
        dest = INBOX_DIR.joinpath(*rel.parts)
        file_bytes = await f.read()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(file_bytes)
        saved.append(str(dest.relative_to(INBOX_DIR)))
    return {"saved": saved, "count": len(saved)}


@router.get("/inbox-files")
def inbox_files():
    return {"files": get_inbox_files()}


@router.post("/assign-manual")
async def manual_assign(
    inbox_path: str = Form(...),
    emp_name:   str = Form(...),
    period:     str = Form(""),
):
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
    from config import DEPT_DIR
    periods = set()
    if DEPT_DIR.exists():
        for p in DEPT_DIR.rglob("*"):
            if p.is_dir() and "-P" in p.name and p.name[:2].isdigit():
                periods.add(p.name)
    return {"periods": sorted(periods)}


@router.delete("/clear-inbox")
def clear_inbox():
    """Delete all files in Inbox/."""
    import shutil
    count = 0
    for f in INBOX_DIR.rglob("*"):
        if f.is_file():
            f.unlink()
            count += 1
    for d in sorted(INBOX_DIR.rglob("*"), reverse=True):
        if d.is_dir():
            try: d.rmdir()
            except: pass
    return {"deleted": count, "location": "Inbox"}


@router.delete("/clear-departments")
def clear_departments():
    """Delete all classified files in Departments/."""
    import shutil
    from config import DEPT_DIR
    count = 0
    for f in DEPT_DIR.rglob("*"):
        if f.is_file():
            f.unlink()
            count += 1
    for d in sorted(DEPT_DIR.rglob("*"), reverse=True):
        if d.is_dir():
            try: d.rmdir()
            except: pass
    return {"deleted": count, "location": "Departments"}


@router.delete("/clear-all")
def clear_all():
    """Clear both Inbox and Departments."""
    from config import DEPT_DIR
    count = 0
    for f in INBOX_DIR.rglob("*"):
        if f.is_file(): f.unlink(); count += 1
    for f in DEPT_DIR.rglob("*"):
        if f.is_file(): f.unlink(); count += 1
    for d in sorted(list(INBOX_DIR.rglob("*")) + list(DEPT_DIR.rglob("*")), reverse=True):
        if d.is_dir():
            try: d.rmdir()
            except: pass
    return {"deleted": count}
