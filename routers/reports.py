from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
import json

from services.report_svc import write_project_f, write_nokia_report
from services.people_svc import find_by_name

router = APIRouter()


def _get_person(emp_name: str) -> dict:
    p = find_by_name(emp_name)
    if not p:
        raise HTTPException(404, f"Employee '{emp_name}' not found")
    return p


@router.post("/report/project-f")
async def write_proj_f(
    emp_name:  str = Form(...),
    tab_json:  str = Form(...),    # {work_days, ess_total, ta_total}
    template:  UploadFile = File(...),
):
    """Write Work Days / ESS / 差旅 into Project F CNS&MN template."""
    p = _get_person(emp_name)
    tab = json.loads(tab_json)
    tb = await template.read()
    try:
        result = write_project_f(
            tb,
            emp_en=p["en"], emp_cn=p.get("cn", ""),
            proj=p.get("proj", ""),
            work_days=tab.get("work_days"),
            ess_total=tab.get("ess_total"),
            ta_total=tab.get("ta_total"),
        )
    except ValueError as e:
        raise HTTPException(404, str(e))

    return StreamingResponse(
        BytesIO(result),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=output_{template.filename}"},
    )


@router.post("/report/nokia-cost")
async def write_nokia_cost(
    emp_name:  str = Form(...),
    tab_json:  str = Form(...),
    template:  UploadFile = File(...),
    sheet_name: str = Form(""),
):
    """
    Write Travel / NS / ESS data into Nokia 費用統整.
    Returns a NEW xlsx WITHOUT formatting (clean data output).

    tab_json keys:
      ta_dates, ta_amount, ns_dates, ns_amount, ess_dates, ess_amount
    """
    p = _get_person(emp_name)
    tab = json.loads(tab_json)
    tb = await template.read()
    try:
        result = write_nokia_report(
            tb,
            emp_en=p["en"], emp_cn=p.get("cn", ""),
            ta_dates=tab.get("ta_dates"),
            ta_amount=tab.get("ta_amount"),
            ns_dates=tab.get("ns_dates"),
            ns_amount=tab.get("ns_amount"),
            ess_dates=tab.get("ess_dates"),
            ess_amount=tab.get("ess_amount"),
            sheet_name=sheet_name or None,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))

    out_name = f"Nokia_費用統整_output.xlsx"
    return StreamingResponse(
        BytesIO(result),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={out_name}"},
    )
