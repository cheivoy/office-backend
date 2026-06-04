from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import json

from services.verify_svc import verify_travel, verify_ot, verify_ns, verify_ess
from services.people_svc import find_by_name

router = APIRouter()


def _get_person(emp_name: str) -> dict:
    p = find_by_name(emp_name)
    if not p:
        raise HTTPException(404, f"Employee '{emp_name}' not found in people list")
    return p


@router.post("/verify/travel")
async def verify_travel_ep(
    emp_name:    str = Form(...),
    tab_ta_json: str = Form(...),          # JSON list of TaEntry dicts
    template:    UploadFile = File(...),
):
    """Cross-check Travel申請 against SNDA Travel DataSheet."""
    p = _get_person(emp_name)
    tab_ta = json.loads(tab_ta_json)
    template_bytes = await template.read()
    result = verify_travel(template_bytes, p["en"], p.get("cn", ""), tab_ta)
    return JSONResponse(result.to_dict())


@router.post("/verify/ot")
async def verify_ot_ep(
    emp_name:    str = Form(...),
    tab_ot_json: str = Form(...),
    template:    UploadFile = File(...),
):
    """Cross-check OT entries against SNDA OT Data sheet."""
    p = _get_person(emp_name)
    tab_ot = json.loads(tab_ot_json)
    template_bytes = await template.read()
    result = verify_ot(template_bytes, p["en"], p.get("cn", ""), tab_ot)
    return JSONResponse(result.to_dict())


@router.post("/verify/ns")
async def verify_ns_ep(
    emp_name:     str = Form(...),
    tab_ess_json: str = Form(...),         # ESS entries; ns_amount > 0 means NS
    template:     UploadFile = File(...),
):
    """Cross-check Night Shift entries against OT_Shift_01June26 sheet."""
    p = _get_person(emp_name)
    tab_ess = json.loads(tab_ess_json)
    template_bytes = await template.read()
    result = verify_ns(template_bytes, p["en"], p.get("cn", ""), tab_ess)
    return JSONResponse(result.to_dict())


@router.post("/verify/ess")
async def verify_ess_ep(
    emp_name:      str = Form(...),
    tab_ess_json:  str = Form(...),
    ess_total:     float = Form(...),
    template:      UploadFile = File(...),
):
    """Cross-check ESS dates and total amount against ESS_ROTA 明細 sheet."""
    p = _get_person(emp_name)
    tab_ess = json.loads(tab_ess_json)
    template_bytes = await template.read()
    result = verify_ess(template_bytes, p["en"], p.get("cn", ""), tab_ess, ess_total)
    return JSONResponse(result.to_dict())


@router.post("/verify/all")
async def verify_all(
    emp_name:      str = Form(...),
    tab_json:      str = Form(...),        # Full form data: {ess, ot, ta}
    travel_file:   UploadFile = File(None),
    ot_file:       UploadFile = File(None),
    ess_file:      UploadFile = File(None),
):
    """
    Run all 4 verifications at once.
    Accepts up to 3 files (can be the same file for OT+NS).
    Returns combined result dict.
    """
    p = _get_person(emp_name)
    tab = json.loads(tab_json)
    en, cn = p["en"], p.get("cn", "")

    results = {}

    if travel_file:
        tb = await travel_file.read()
        results["travel"] = verify_travel(tb, en, cn, tab.get("ta", [])).to_dict()

    if ot_file:
        ob = await ot_file.read()
        results["ot"] = verify_ot(ob, en, cn, tab.get("ot", [])).to_dict()
        results["ns"] = verify_ns(ob, en, cn, tab.get("ns", tab.get("ess", []))).to_dict()

    if ess_file:
        eb = await ess_file.read()
        ess_total = sum(float(e.get("amount") or 0) for e in tab.get("ess", []))
        results["ess"] = verify_ess(eb, en, cn, tab.get("ess", []), ess_total).to_dict()

    return JSONResponse(results)
