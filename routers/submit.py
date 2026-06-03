from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
import json

from models.schemas import SubmitPayload, OtEntry
from services.excel_svc import write_cht, write_wipro

router = APIRouter()


@router.post("/submit-data")
async def submit_data(
    payload_json: str = Form(...),
    template:     UploadFile = File(...),
):
    """
    Accepts multipart/form-data:
      - payload_json: JSON string matching SubmitPayload
      - template:     the current month's .xlsx file

    Returns the modified Excel file for download.
    """
    try:
        payload = SubmitPayload(**json.loads(payload_json))
    except Exception as e:
        raise HTTPException(422, f"Invalid payload: {e}")

    template_bytes = await template.read()

    try:
        if payload.write_target in ("cht_nokia", "cht_dk"):
            result_bytes = write_cht(template_bytes, payload)
            out_name = f"output_{template.filename}"
        elif payload.write_target == "wipro_snda":
            # Wipro: pull fields from payload
            ess_total   = sum(e.amount or 0 for e in payload.ess)
            shift_total = sum(e.ns_amount or 0 for e in payload.ess)
            ta_total    = sum(t.amount or 0 for t in payload.ta)
            result_bytes = write_wipro(
                template_bytes,
                emp_en=payload.emp_en,
                ess=ess_total,
                shift=shift_total,
                ot_entries=payload.ot,
                travel=ta_total,
            )
            out_name = f"output_{template.filename}"
        else:
            raise HTTPException(400, f"Unknown write_target: {payload.write_target}")
    except ValueError as e:
        raise HTTPException(404, str(e))

    return StreamingResponse(
        BytesIO(result_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={out_name}"},
    )


@router.post("/submit-wipro")
async def submit_wipro(
    payload_json: str = Form(...),
    template:     UploadFile = File(...),
    sheet_name:   str = Form(""),
):
    """Dedicated Wipro SNDA endpoint with optional sheet_name (e.g. P06_26)."""
    data = json.loads(payload_json)
    template_bytes = await template.read()
    ot_entries = [OtEntry(**o) for o in data.get("ot", [])]
    try:
        result_bytes = write_wipro(
            template_bytes,
            emp_en=data["emp_en"],
            ess=data.get("ess_amount", 0),
            shift=data.get("shift_amount", 0),
            ot_entries=ot_entries,
            travel=data.get("travel_amount", 0),
            sheet_name=sheet_name or None,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))

    out_name = f"output_{template.filename}"
    return StreamingResponse(
        BytesIO(result_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={out_name}"},
    )
