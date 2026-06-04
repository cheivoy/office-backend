import zipfile
from io import BytesIO
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from services.scan_svc import _emp_dir
from services.people_svc import find_by_name

router = APIRouter()


@router.get("/preview-file/{emp_en}/{file_path:path}")
def preview_file(emp_en: str, file_path: str):
    person = find_by_name(emp_en)
    if not person:
        raise HTTPException(404, "Employee not found")
    emp_dir = _emp_dir(person)
    # Try exact relative path first
    path = emp_dir / file_path
    if not path.exists():
        # Fallback: search by filename anywhere under emp_dir
        fname = Path(file_path).name
        matches = list(emp_dir.rglob(fname))
        if matches:
            path = matches[0]
    if not path.exists():
        raise HTTPException(404, f"File not found: {file_path}")
    suffix = path.suffix.lower()
    media = {
        ".pdf":  "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls":  "application/vnd.ms-excel",
        ".eml":  "message/rfc822",
        ".msg":  "application/vnd.ms-outlook",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png":  "image/png",
    }.get(suffix, "application/octet-stream")
    return FileResponse(str(path), media_type=media, filename=path.name)

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


@router.delete("/delete-file/{emp_en}/{file_path:path}")
def delete_file(emp_en: str, file_path: str):
    """Delete a single file from an employee's folder."""
    person = find_by_name(emp_en)
    if not person:
        raise HTTPException(404, "Employee not found")
    emp_dir = _emp_dir(person)
    path = emp_dir / file_path
    if not path.exists():
        # Fallback: search by filename
        fname = Path(file_path).name
        matches = list(emp_dir.rglob(fname))
        if matches:
            path = matches[0]
    if not path.exists():
        raise HTTPException(404, f"File not found: {file_path}")
    path.unlink()
    # Remove empty parent dirs up to emp_dir
    parent = path.parent
    while parent != emp_dir and parent.exists():
        try: parent.rmdir(); parent = parent.parent
        except OSError: break
    return {"deleted": file_path}

@router.post("/move-file")
async def move_file(
    file_path:   str = Form(...),   # relative path under emp dir
    emp_en:      str = Form(""),    # source employee en name (or use emp_id)
    target_emp:  str = Form(""),    # destination employee en name (or use target_id)
    target_period: str = Form(""),  # optional period folder
    do_copy:     bool = Form(False),# True = copy, False = move
    emp_id:        str = Form(""),   # optional source id (preferred)
    target_id:     str = Form(""),   # optional target id (preferred)
):
    """Move or copy a file from one employee folder to another."""
    from services.people_svc import find_by_name, find_by_id
    from services.scan_svc import _emp_dir, _safe_dest
    from config import DEPT_DIR
    import shutil

    src_id = int(emp_id) if emp_id.strip().isdigit() else None
    dst_id = int(target_id) if target_id.strip().isdigit() else None
    src_person = (find_by_id(src_id) if src_id is not None
                  else find_by_name(emp_en, target_period) or find_by_name(emp_en))
    dst_person = (find_by_id(dst_id) if dst_id is not None
                  else find_by_name(target_emp, target_period) or find_by_name(target_emp))
    if not src_person: raise HTTPException(404, f"Source employee '{emp_en}' not found")
    if not dst_person:  raise HTTPException(404, f"Target employee '{target_emp}' not found")

    src_emp_dir = _emp_dir(src_person)
    src_path = src_emp_dir / file_path
    if not src_path.exists():
        fname = Path(file_path).name
        matches = list(src_emp_dir.rglob(fname))
        if matches:
            src_path = matches[0]
    if not src_path.exists(): raise HTTPException(404, "Source file not found")

    dst_dir = _emp_dir(dst_person) / target_period if target_period else _emp_dir(dst_person)
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst_path = _safe_dest(dst_dir / src_path.name)

    if do_copy:
        shutil.copy2(str(src_path), str(dst_path))
    else:
        shutil.move(str(src_path), str(dst_path))

    return {
        "action":  "copy" if do_copy else "move",
        "from":    str(src_path.relative_to(DEPT_DIR)),
        "to":      str(dst_path.relative_to(DEPT_DIR)),
    }


@router.post("/upload-to-employee")
async def upload_to_employee(
    emp_en:  str = Form(...),
    period:  str = Form(""),
    files:   list[UploadFile] = File(...),
):
    """Directly upload files to a specific employee folder (skips Inbox)."""
    from services.people_svc import find_by_name
    from services.scan_svc import _emp_dir, _safe_dest, _detect_type
    # 先用 period 名單找；找不到再退回全域名單（新人可能只在月份名單裡）
    person = find_by_name(emp_en, period) or find_by_name(emp_en)
    if not person: raise HTTPException(404, f"Employee '{emp_en}' not found")

    emp_dir = _emp_dir(person)
    dest_dir = emp_dir / period if period else emp_dir
    dest_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for f in files:
        dest = _safe_dest(dest_dir / f.filename)
        content = await f.read()
        dest.write_bytes(content)
        saved.append({
            "name":  dest.name,
            "ftype": _detect_type(dest.name),
            "path":  str(dest.relative_to(emp_dir)),
        })
    return {"saved": saved, "count": len(saved)}