"""
sync_svc.py — 填寫資料 & 進度追蹤 持久化服務（優化版）

優化項目：
1. updated_at timestamp — 每筆資料帶時間戳，後端拒絕以舊資料覆蓋新資料
2. 按 period 篩選 — GET /api/forms?period=2026-P05 只回傳該月有資料的員工
3. atomic write — 先寫 .tmp 再 rename，防止寫到一半當機造成資料損毀
4. in-memory cache — 同一 process 內快取，避免每次 API call 都讀磁碟

forms.json 格式：
{
  "Johnson_Chou": {
    "updated_at": "2026-05-20T10:30:00",
    "workdays": 20,
    "checkedSecs": ["tr", "ess"],
    "ess": [...], "ot": [...], "ta": [...], "leave": []
  }
}

progress.json 格式：
{
  "CNS||wipro": {
    "updated_at": "2026-05-20T10:30:00",
    "service_tr_collect": { "checked": true, "note": "", "filename": "" },
    ...
  }
}
"""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from config import FORMS_JSON, PROGRESS_JSON

# ── In-memory cache ───────────────────────────────────────────────────────────
_cache: dict[str, dict] = {}          # path_str -> parsed dict
_cache_mtime: dict[str, float] = {}   # path_str -> last mtime when cached
_lock = threading.Lock()              # protect concurrent reads/writes


# ── Core I/O ─────────────────────────────────────────────────────────────────

def _read(path: Path) -> dict:
    """Read JSON with in-memory cache. Refreshes if file changed on disk."""
    key = str(path)
    try:
        mtime = path.stat().st_mtime if path.exists() else 0.0
    except OSError:
        mtime = 0.0

    with _lock:
        if key in _cache and _cache_mtime.get(key) == mtime:
            return dict(_cache[key])          # return shallow copy

    # Cache miss or stale — read from disk
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = {}
    except Exception:
        data = {}

    with _lock:
        _cache[key] = data
        _cache_mtime[key] = mtime

    return dict(data)


def _write(path: Path, data: dict) -> None:
    """Atomic write: write to .tmp then rename, so partial writes never corrupt data."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(path))   # atomic on POSIX & Windows

    # Update cache immediately after write
    key = str(path)
    with _lock:
        _cache[key] = data
        try:
            _cache_mtime[key] = path.stat().st_mtime
        except OSError:
            pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _is_newer(incoming_ts: str | None, existing_ts: str | None) -> bool:
    """Return True if incoming_ts >= existing_ts (or existing has no timestamp)."""
    if not existing_ts:
        return True
    if not incoming_ts:
        return False
    return incoming_ts >= existing_ts


# ── Forms ─────────────────────────────────────────────────────────────────────

def get_all_forms(period: str = "") -> dict:
    """
    Return all forms, optionally filtered by period.
    period e.g. "2026-P05" — only employees whose form's `period` field matches.
    """
    all_forms = _read(FORMS_JSON)
    if not period:
        return all_forms
    # Filter: return employees who have data tagged for this period
    return {
        en: data for en, data in all_forms.items()
        if data.get("period") == period or not data.get("period")
    }


def get_form(emp_en: str) -> dict | None:
    return _read(FORMS_JSON).get(emp_en)


def save_form(emp_en: str, form_data: dict) -> dict:
    """
    Save single employee form.
    Rejects if incoming updated_at < existing updated_at (stale write protection).
    Returns saved data or raises ValueError on conflict.
    """
    all_forms = _read(FORMS_JSON)
    existing = all_forms.get(emp_en, {})

    incoming_ts = form_data.get("updated_at")
    existing_ts = existing.get("updated_at")

    if not _is_newer(incoming_ts, existing_ts):
        raise ValueError(
            f"Conflict: incoming data ({incoming_ts}) is older than "
            f"server data ({existing_ts}). Fetch latest first."
        )

    # Stamp with server time before saving
    form_data["updated_at"] = _now_iso()
    all_forms[emp_en] = form_data
    _write(FORMS_JSON, all_forms)
    return form_data


def save_forms_bulk(forms: dict) -> dict:
    """
    Save multiple employees' forms (dirty-only sync).
    Each entry is checked individually against its existing timestamp.
    Returns counts of saved vs skipped (conflict).
    """
    all_forms = _read(FORMS_JSON)
    saved, skipped = [], []
    server_ts = _now_iso()

    for emp_en, form_data in forms.items():
        existing = all_forms.get(emp_en, {})
        incoming_ts = form_data.get("updated_at")
        existing_ts = existing.get("updated_at")

        if _is_newer(incoming_ts, existing_ts):
            form_data["updated_at"] = server_ts
            all_forms[emp_en] = form_data
            saved.append(emp_en)
        else:
            skipped.append(emp_en)

    _write(FORMS_JSON, all_forms)
    return {
        "saved": saved,
        "skipped": skipped,
        "saved_count": len(saved),
        "skipped_count": len(skipped),
    }


def delete_form(emp_en: str) -> bool:
    all_forms = _read(FORMS_JSON)
    if emp_en in all_forms:
        del all_forms[emp_en]
        _write(FORMS_JSON, all_forms)
        return True
    return False


# ── Progress ──────────────────────────────────────────────────────────────────

def get_all_progress() -> dict:
    return _read(PROGRESS_JSON)


def get_progress(unit_key: str) -> dict | None:
    return _read(PROGRESS_JSON).get(unit_key)


def save_progress(unit_key: str, progress_data: dict) -> dict:
    """Save single unit progress with conflict protection."""
    all_progress = _read(PROGRESS_JSON)
    existing = all_progress.get(unit_key, {})

    incoming_ts = progress_data.get("updated_at")
    existing_ts = existing.get("updated_at")

    if not _is_newer(incoming_ts, existing_ts):
        raise ValueError(
            f"Conflict: incoming progress ({incoming_ts}) is older than "
            f"server ({existing_ts})."
        )

    progress_data["updated_at"] = _now_iso()
    all_progress[unit_key] = progress_data
    _write(PROGRESS_JSON, all_progress)
    return progress_data


def save_progress_bulk(progress: dict) -> dict:
    """Save all progress units, check timestamps individually."""
    all_progress = _read(PROGRESS_JSON)
    saved, skipped = [], []
    server_ts = _now_iso()

    for unit_key, p_data in progress.items():
        existing = all_progress.get(unit_key, {})
        incoming_ts = p_data.get("updated_at")
        existing_ts = existing.get("updated_at")

        if _is_newer(incoming_ts, existing_ts):
            p_data["updated_at"] = server_ts
            all_progress[unit_key] = p_data
            saved.append(unit_key)
        else:
            skipped.append(unit_key)

    _write(PROGRESS_JSON, all_progress)
    return {
        "saved": saved,
        "skipped": skipped,
        "saved_count": len(saved),
        "skipped_count": len(skipped),
    }
