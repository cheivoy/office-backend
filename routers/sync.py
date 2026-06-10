"""
sync.py — 填寫資料 & 進度追蹤 API（優化版）

新增：
  GET /api/forms?period=2026-P05   按月份篩選，減少回傳資料量
  PUT /api/forms/{emp_en}          有衝突時回傳 409 而非靜默覆蓋
  PUT /api/forms                   bulk 同步，回傳 saved/skipped 清單
"""
from fastapi import APIRouter, Request, HTTPException
from services import sync_svc

router = APIRouter()


# ── Forms ─────────────────────────────────────────────────────────────────────

@router.get("/forms")
def get_all_forms(period: str = ""):
    """
    取得填寫資料。
    - period="" → 全部
    - period="2026-P05" → 只回傳該月資料（大幅減少資料量）
    """
    return sync_svc.get_all_forms(period=period)


@router.get("/forms/history/{emp_en}")
def get_form_history(emp_en: str, before: str = ""):
    """
    跨月歷史：回傳該員工 `before` 月份之前的所有 tab 記錄。
    例：核對 2026-P05 時，呼叫 ?before=2026-P05 取得 P04（及更早）資料做重複偵測。
    回傳 { period: form, ... }（新到舊）。
    """
    return sync_svc.get_form_history(emp_en, before=before)


@router.get("/forms/{emp_en}")
def get_form(emp_en: str, period: str = ""):
    data = sync_svc.get_form(emp_en, period=period)
    return data if data is not None else {}


@router.put("/forms/{emp_en}")
async def save_form(emp_en: str, request: Request):
    body = await request.json()
    try:
        return sync_svc.save_form(emp_en, body)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/forms")
async def save_forms_bulk(request: Request):
    """
    Bulk sync — only dirty employees.
    回傳 { saved: [...], skipped: [...], saved_count, skipped_count }
    skipped 表示後端有更新版本，前端需要重新拉取。
    """
    body = await request.json()
    return sync_svc.save_forms_bulk(body)


@router.delete("/forms/{emp_en}")
def delete_form(emp_en: str, period: str = ""):
    deleted = sync_svc.delete_form(emp_en, period=period)
    return {"deleted": deleted, "emp_en": emp_en, "period": period}


# ── Progress ──────────────────────────────────────────────────────────────────

@router.get("/progress")
def get_all_progress():
    return sync_svc.get_all_progress()


@router.get("/progress/{unit_key:path}")
def get_progress(unit_key: str):
    data = sync_svc.get_progress(unit_key)
    return data if data is not None else {}


@router.put("/progress/{unit_key:path}")
async def save_progress(unit_key: str, request: Request):
    body = await request.json()
    try:
        return sync_svc.save_progress(unit_key, body)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/progress")
async def save_progress_bulk(request: Request):
    body = await request.json()
    return sync_svc.save_progress_bulk(body)
