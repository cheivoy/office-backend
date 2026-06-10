"""
batch_write_svc.py — Batch write to Excel templates.

For fixed templates (CHT Nokia, DK): reads from server templates/ folder.
For monthly templates (SNDA, Project F, Nokia Cost): caller provides bytes.
"""
from __future__ import annotations
import zipfile
from io import BytesIO
from pathlib import Path

from config import CHT_NOKIA_DIR, CHT_DK_DIR, CHT_NOKIA_PM_FILES, CHT_DK_TEMPLATE
from services.people_svc import get_all
from services.excel_svc import write_cht, write_wipro
from services.report_svc import write_project_f, write_nokia_report
from models.schemas import SubmitPayload, OtEntry, LeaveEntry


def _get_form(forms: dict, emp_en: str) -> dict:
    """Get form data for an employee by English name (case-insensitive)."""
    for key, val in forms.items():
        if key.lower() == emp_en.lower():
            return val
    return {}


def batch_write_cht_nokia(period: str, forms: dict[str, dict]) -> tuple[bytes, dict]:
    """
    Write all CHT Nokia employees into their respective PM files.
    Returns (zip_bytes, report).
    report = {written, skipped:[{emp,reason}], pm_files_missing:[...], ...}
    forms: {emp_en: {work_days, ess, ot, ta, leave, ...}}
    """
    people = get_all()
    cht_emps = [p for p in people if p.get("unit") == "CHT" and p.get("pm") != "DK"]

    report = {"target": "cht_nokia", "written": 0, "skipped": [],
              "pm_files_missing": [], "people_total": len(cht_emps)}

    # Group by PM
    pm_groups: dict[str, list[dict]] = {}
    for emp in cht_emps:
        pm = emp.get("pm", "")
        pm_groups.setdefault(pm, []).append(emp)

    buf = BytesIO()
    any_template = False
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for pm, emps in pm_groups.items():
            tpl_name = CHT_NOKIA_PM_FILES.get(pm)
            tpl_path = CHT_NOKIA_DIR / tpl_name if tpl_name else None
            if not tpl_path or not tpl_path.exists():
                # Record exactly why this whole PM group produced nothing
                reason = (f"PM「{pm}」沒有對應範本名稱（config.CHT_NOKIA_PM_FILES）"
                          if not tpl_name
                          else f"範本檔不存在：templates/cht_nokia/{tpl_name}")
                report["pm_files_missing"].append({"pm": pm, "reason": reason})
                for emp in emps:
                    report["skipped"].append({"emp": emp["en"], "reason": reason})
                continue

            any_template = True
            template_bytes = tpl_path.read_bytes()
            for emp in emps:
                f = _get_form(forms, emp["en"])
                if not f:
                    report["skipped"].append(
                        {"emp": emp["en"], "reason": "沒有填寫資料（forms 中找不到）"})
                    continue
                payload = _build_payload(emp, f)
                try:
                    template_bytes = write_cht(template_bytes, payload)
                    report["written"] += 1
                except ValueError as e:
                    report["skipped"].append(
                        {"emp": emp["en"], "reason": f"範本中找不到此員工列（{e}）"})

            out_name = f"{period}_{tpl_name}" if period else tpl_name
            zf.writestr(out_name, template_bytes)

    if not any_template:
        # Every PM template was missing → don't hand back an empty zip silently.
        raise FileNotFoundError(
            "找不到任何 Nokia 工作天數表範本。請確認 templates/cht_nokia/ "
            "底下有對應 PM 的 .xlsx，且 config.CHT_NOKIA_PM_FILES 的 PM 名稱與名單一致。"
        )

    buf.seek(0)
    return buf.getvalue(), report


def batch_write_cht_dk(period: str, forms: dict[str, dict]) -> tuple[bytes, dict]:
    """Write all DK employees into the single DK template. Returns (bytes, report)."""
    people  = get_all()
    dk_emps = [p for p in people if p.get("pm") == "DK"]
    report = {"target": "cht_dk", "written": 0, "skipped": [], "people_total": len(dk_emps)}

    tpl_path = CHT_DK_DIR / CHT_DK_TEMPLATE
    if not tpl_path.exists():
        raise FileNotFoundError(f"DK 範本不存在：templates/cht_dk/{CHT_DK_TEMPLATE}")

    template_bytes = tpl_path.read_bytes()
    for emp in dk_emps:
        f = _get_form(forms, emp["en"])
        if not f:
            report["skipped"].append({"emp": emp["en"], "reason": "沒有填寫資料"})
            continue
        payload = _build_payload(emp, f, write_target="cht_dk")
        try:
            template_bytes = write_cht(template_bytes, payload)
            report["written"] += 1
        except ValueError as e:
            report["skipped"].append({"emp": emp["en"], "reason": f"範本中找不到此員工列（{e}）"})

    return template_bytes, report


def batch_write_wipro(template_bytes: bytes, sheet_name: str,
                      forms: dict[str, dict]) -> tuple[bytes, dict]:
    """Write all Wipro employees into SNDA Dashboard. Returns (bytes, report)."""
    people     = get_all()
    wipro_emps = [p for p in people if p.get("unit") == "wipro"]
    report = {"target": "wipro", "written": 0, "skipped": [], "people_total": len(wipro_emps)}

    for emp in wipro_emps:
        f = _get_form(forms, emp["en"])
        if not f:
            report["skipped"].append({"emp": emp["en"], "reason": "沒有填寫資料"})
            continue
        ess_total   = sum(float(e.get("amount") or 0) for e in f.get("ess", []))
        shift_total = sum(float(e.get("amount") or 0) for e in f.get("ns", []))
        ta_total    = sum(float(t.get("amount") or 0) for t in f.get("ta", []))
        ot_entries  = [OtEntry(**o) for o in f.get("ot", [])]
        try:
            template_bytes = write_wipro(
                template_bytes, emp["en"],
                ess=ess_total, shift=shift_total,
                ot_entries=ot_entries, travel=ta_total,
                sheet_name=sheet_name,
            )
            report["written"] += 1
        except ValueError as e:
            report["skipped"].append({"emp": emp["en"], "reason": f"範本中找不到此員工列（{e}）"})

    return template_bytes, report


def batch_write_project_f(template_bytes: bytes, forms: dict[str, dict]) -> tuple[bytes, dict]:
    """Write all employees into Project F. Returns (bytes, report)."""
    people = get_all()
    report = {"target": "project_f", "written": 0, "skipped": [], "people_total": len(people)}
    for emp in people:
        f = _get_form(forms, emp["en"])
        if not f:
            continue  # Project F covers everyone; no-data is normal, don't spam report
        try:
            template_bytes = write_project_f(
                template_bytes,
                emp_en=emp["en"], emp_cn=emp.get("cn", ""),
                proj=emp.get("proj", ""),
                work_days=float(f.get("workdays") or 0) or None,
                ess_total=sum(float(e.get("amount") or 0) for e in f.get("ess", [])),
                ta_total=sum(float(t.get("amount") or 0) for t in f.get("ta", [])),
            )
            report["written"] += 1
        except ValueError as e:
            report["skipped"].append({"emp": emp["en"], "reason": f"範本中找不到此員工列（{e}）"})
    return template_bytes, report


def batch_write_nokia_cost(template_bytes: bytes, sheet_name: str,
                           forms: dict[str, dict]) -> tuple[bytes, dict]:
    """Write all employees into Nokia 費用統整. Returns (bytes, report)."""
    people = get_all()
    report = {"target": "nokia_cost", "written": 0, "skipped": [], "people_total": len(people)}
    for emp in people:
        f = _get_form(forms, emp["en"])
        if not f:
            continue
        ta_rows  = f.get("ta", [])
        ess_rows = f.get("ess", [])
        ns_rows  = f.get("ns", [])

        def fmt_dates(rows, key="from_date"):
            return "  ".join(r.get(key, "").replace("-", "")[4:] for r in rows if r.get(key))

        ta_dates  = fmt_dates(ta_rows, "from_date")
        # NS now lives in its own array keyed by single `date`
        ns_dates  = "  ".join(r.get("date", "")[5:].replace("-", "")
                              for r in ns_rows if r.get("date"))
        # ESS uses a date range (from_date) now
        ess_dates = fmt_dates(ess_rows, "from_date")

        try:
            template_bytes = write_nokia_report(
                template_bytes,
                emp_en=emp["en"], emp_cn=emp.get("cn", ""),
                ta_dates=ta_dates or None,
                ta_amount=sum(float(t.get("amount") or 0) for t in ta_rows) or None,
                ns_dates=ns_dates or None,
                ns_amount=sum(float(e.get("amount") or 0) for e in ns_rows) or None,
                ess_dates=ess_dates or None,
                ess_amount=sum(float(e.get("amount") or 0) for e in ess_rows) or None,
                sheet_name=sheet_name or None,
            )
            report["written"] += 1
        except ValueError as e:
            report["skipped"].append({"emp": emp["en"], "reason": f"範本中找不到此員工列（{e}）"})
    return template_bytes, report


def _build_payload(emp: dict, f: dict, write_target: str = "cht_nokia") -> SubmitPayload:
    from models.schemas import EssEntry, NsEntry, OtEntry, TaEntry, LeaveEntry
    return SubmitPayload(
        emp_name=emp.get("cn") or emp["en"],
        emp_en=emp["en"],
        work_days=float(f.get("workdays") or 0) or None,
        ess=[EssEntry(**e) for e in f.get("ess", [])],
        ns=[NsEntry(**n) for n in f.get("ns", [])],
        ot=[OtEntry(**o) for o in f.get("ot", [])],
        ta=[TaEntry(**t) for t in f.get("ta", [])],
        leave=[LeaveEntry(**lv) for lv in f.get("leave", [])],
        write_target=write_target,
    )
