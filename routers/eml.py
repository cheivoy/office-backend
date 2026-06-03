from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, JSONResponse
from services.eml_svc import parse_eml, extract_attachment, get_eml_bytes
from services.scan_svc import _emp_dir
from services.people_svc import find_by_name

router = APIRouter()


@router.get("/eml/preview/{emp_en}/{filename}")
def eml_preview(emp_en: str, filename: str):
    """Parse an .eml and return structured JSON for frontend rendering."""
    person = find_by_name(emp_en)
    if not person:
        raise HTTPException(404, "Employee not found")
    raw = get_eml_bytes(_emp_dir(person), filename)
    if raw is None:
        raise HTTPException(404, "EML file not found")
    return JSONResponse(parse_eml(raw))


@router.get("/eml/attachment/{emp_en}/{filename}/{attachment_name}")
def eml_attachment(emp_en: str, filename: str, attachment_name: str):
    """Download a specific attachment from an .eml file."""
    person = find_by_name(emp_en)
    if not person:
        raise HTTPException(404, "Employee not found")
    raw = get_eml_bytes(_emp_dir(person), filename)
    if raw is None:
        raise HTTPException(404, "EML file not found")
    data = extract_attachment(raw, attachment_name)
    if data is None:
        raise HTTPException(404, f"Attachment '{attachment_name}' not found")
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={attachment_name}"},
    )
