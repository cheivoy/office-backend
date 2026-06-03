import zipfile
from io import BytesIO
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from services.scan_svc import _emp_dir
from services.people_svc import find_by_name

router = APIRouter()


@router.get("/preview-file/{emp_en}/{filename}")
def preview_file(emp_en: str, filename: str):
    person = find_by_name(emp_en)
    if not person:
        raise HTTPException(404, "Employee not found")
    path = _emp_dir(person) / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    suffix = path.suffix.lower()
    media = {
        ".pdf":  "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".eml":  "message/rfc822",
    }.get(suffix, "application/octet-stream")
    return FileResponse(str(path), media_type=media, filename=filename)


@router.get("/download-zip/{emp_en}")
def download_zip(emp_en: str):
    person = find_by_name(emp_en)
    if not person:
        raise HTTPException(404, "Employee not found")
    emp_dir = _emp_dir(person)
    if not emp_dir.exists():
        raise HTTPException(404, "No files found")
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in emp_dir.iterdir():
            if f.is_file():
                zf.write(f, f.name)
    buf.seek(0)
    name = f"{person['en'].replace(' ','_')}_files.zip"
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f"attachment; filename={name}"})


@router.get("/download-all-zip")
def download_all_zip():
    from config import DEPT_DIR
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in DEPT_DIR.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(DEPT_DIR))
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": "attachment; filename=all_departments.zip"})
