"""
sync_svc.py — 填寫資料 & 進度追蹤 持久化服務（優化版）

優化項目：
1. updated_at timestamp — 每筆資料帶時間戳，後端拒絕以舊資料覆蓋新資料
2. 按 period 篩選 — GET /api/forms?period=2026-P05 只回傳該月有資料的員工
3. atomic write — 先寫 .tmp 再 rename，防止寫到一半當機造成資料損毀
4. in-memory cache — 同一 process 內快取，避免每次 API call 都讀磁碟

forms.json 格式（v2：按月份分層，保留跨月歷史）：
{
  "2026-P04": {
    "Johnson_Chou": {
      "updated_at": "2026-04-20T10:30:00",
      "workdays": 20, "checkedSecs": ["tr"], "ess": [...], "ot": [...], "ta": [...], "leave": []
    }
  },
  "2026-P05": {
    "Johnson_Chou": { ... }
  }
}

v1 → v2 自動遷移：
  舊格式是「每人一份、會被新月份覆蓋」的扁平結構：
    { "Johnson_Chou": { workdays, ess, ... , "period": "2026-P05"? } }
  載入時若偵測到頂層的值看起來是「員工資料」而非「月份分層」，
  會把它搬到對應的 period 之下（資料若帶 period 欄位用之，否則歸到 LEGACY_PERIOD）。
  遷移只做一次，之後寫回即為 v2 結構。

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


# ── Forms (period-layered v2) ─────────────────────────────────────────────────

LEGACY_PERIOD = "_legacy"   # bucket for old data that had no period tag
DEFAULT_PERIOD = "_unfiled" # fallback when a save arrives without a period


def _looks_like_form(value) -> bool:
    """Heuristic: does this dict look like a single employee's form (v1)
    rather than a period bucket (v2)?  v1 form has form-ish keys; a period
    bucket's values are themselves dicts keyed by emp_en."""
    if not isinstance(value, dict):
        return False
    form_keys = {"workdays", "ess", "ot", "ta", "leave", "ns",
                 "checkedSecs", "updated_at", "period"}
    return bool(form_keys & set(value.keys()))


def _migrate_if_needed(data: dict) -> tuple[dict, bool]:
    """
    Return (v2_data, changed).
    v2 shape: { period: { emp_en: form } }.
    If `data` is detected as the old flat v1 shape ({ emp_en: form }),
    move each employee under its own period (data["period"]) or LEGACY_PERIOD.
    """
    if not data:
        return {}, False

    # If every top-level value is a period bucket (dict of forms), it's v2.
    # We detect v1 by finding any top-level value that looks like a form itself.
    is_v1 = any(_looks_like_form(v) for v in data.values())
    if not is_v1:
        return data, False

    migrated: dict[str, dict] = {}
    for emp_en, form in data.items():
        if not isinstance(form, dict):
            continue
        period = form.get("period") or LEGACY_PERIOD
        migrated.setdefault(period, {})[emp_en] = form
    return migrated, True


def _load_forms() -> dict:
    """Load forms.json, auto-migrating v1→v2 and persisting the migration once."""
    data = _read(FORMS_JSON)
    migrated, changed = _migrate_if_needed(data)
    if changed:
        _write(FORMS_JSON, migrated)
    return migrated


def get_all_forms(period: str = "") -> dict:
    """
    Return forms for a given period as { emp_en: form }.
    - period="" → returns the WHOLE v2 structure { period: { emp_en: form } }
      (kept for admin/debug; the frontend always passes a period).
    - period="2026-P05" → returns just that month's { emp_en: form }.
    """
    all_forms = _load_forms()
    if not period:
        return all_forms
    return dict(all_forms.get(period, {}))


def get_form(emp_en: str, period: str = "") -> dict | None:
    all_forms = _load_forms()
    if period:
        return all_forms.get(period, {}).get(emp_en)
    # No period: search newest period that has this employee
    for p in sorted(all_forms.keys(), reverse=True):
        if emp_en in all_forms[p]:
            return all_forms[p][emp_en]
    return None


def get_form_history(emp_en: str, before: str = "") -> dict:
    """
    Return this employee's forms from periods strictly BEFORE `before`.
    Used for cross-month duplicate detection (e.g. verifying P05 → look at P04).
    Returns { period: form, ... } sorted newest-first.
    If `before` is empty, returns ALL periods for this employee.
    """
    all_forms = _load_forms()
    out = {}
    for p in sorted(all_forms.keys(), reverse=True):
        if p in (LEGACY_PERIOD, DEFAULT_PERIOD):
            # legacy/unfiled has no comparable period ordering; include only
            # when no `before` filter is set
            if before:
                continue
        elif before and not (p < before):
            continue
        form = all_forms[p].get(emp_en)
        if form is not None:
            out[p] = form
    return out


def save_form(emp_en: str, form_data: dict) -> dict:
    """
    Save single employee form into its period bucket.
    period is read from form_data["period"]; falls back to DEFAULT_PERIOD.
    Stale-write protection is per (period, emp_en).
    """
    all_forms = _load_forms()
    period = form_data.get("period") or DEFAULT_PERIOD
    bucket = all_forms.setdefault(period, {})
    existing = bucket.get(emp_en, {})

    incoming_ts = form_data.get("updated_at")
    existing_ts = existing.get("updated_at")
    if not _is_newer(incoming_ts, existing_ts):
        raise ValueError(
            f"Conflict: incoming data ({incoming_ts}) is older than "
            f"server data ({existing_ts}). Fetch latest first."
        )

    form_data["updated_at"] = _now_iso()
    form_data["period"] = period
    bucket[emp_en] = form_data
    _write(FORMS_JSON, all_forms)
    return form_data


def save_forms_bulk(forms: dict) -> dict:
    """
    Bulk save (dirty-only). Each form is routed to its own period bucket
    (forms[emp_en]["period"]). Stale-write protection per (period, emp_en).
    """
    all_forms = _load_forms()
    saved, skipped = [], []
    server_ts = _now_iso()

    for emp_en, form_data in forms.items():
        period = form_data.get("period") or DEFAULT_PERIOD
        bucket = all_forms.setdefault(period, {})
        existing = bucket.get(emp_en, {})
        incoming_ts = form_data.get("updated_at")
        existing_ts = existing.get("updated_at")

        if _is_newer(incoming_ts, existing_ts):
            form_data["updated_at"] = server_ts
            form_data["period"] = period
            bucket[emp_en] = form_data
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


def delete_form(emp_en: str, period: str = "") -> bool:
    all_forms = _load_forms()
    removed = False
    if period:
        if emp_en in all_forms.get(period, {}):
            del all_forms[period][emp_en]
            removed = True
    else:
        for p in list(all_forms.keys()):
            if emp_en in all_forms[p]:
                del all_forms[p][emp_en]
                removed = True
    if removed:
        _write(FORMS_JSON, all_forms)
    return removed


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
