"""
eml_svc.py — Parse .eml files and extract attachments.
"""
from __future__ import annotations
import email
import email.policy
from pathlib import Path


def parse_eml(eml_bytes: bytes) -> dict:
    """
    Parse an .eml file and return:
    {
      "from": str, "to": str, "subject": str, "date": str,
      "body": str,
      "attachments": [{"filename": str, "content_type": str, "size": int}]
    }
    """
    msg = email.message_from_bytes(eml_bytes, policy=email.policy.default)

    body_parts = []
    attachments = []

    for part in msg.walk():
        ct = part.get_content_type()
        cd = str(part.get("Content-Disposition") or "")
        filename = part.get_filename()

        if "attachment" in cd or filename:
            attachments.append({
                "filename": filename or "attachment",
                "content_type": ct,
                "size": len(part.get_payload(decode=True) or b""),
            })
        elif ct == "text/plain" and "attachment" not in cd:
            try:
                body_parts.append(part.get_content())
            except Exception:
                body_parts.append(str(part.get_payload(decode=True) or b"", "utf-8", errors="replace"))

    return {
        "from":        str(msg.get("From") or ""),
        "to":          str(msg.get("To") or ""),
        "subject":     str(msg.get("Subject") or ""),
        "date":        str(msg.get("Date") or ""),
        "body":        "\n".join(body_parts).strip(),
        "attachments": attachments,
    }


def extract_attachment(eml_bytes: bytes, filename: str) -> bytes | None:
    """Extract a specific attachment by filename, return raw bytes."""
    msg = email.message_from_bytes(eml_bytes, policy=email.policy.default)
    for part in msg.walk():
        if part.get_filename() == filename:
            return part.get_payload(decode=True)
    return None


def get_eml_bytes(emp_dir: Path, eml_path: str) -> bytes | None:
    path = emp_dir / eml_path
    if not path.exists():
        # fallback: search recursively by filename
        name = Path(eml_path).name
        matches = list(emp_dir.rglob(name))
        path = matches[0] if matches else path
    if path.exists() and path.suffix.lower() == ".eml":
        return path.read_bytes()
    return None
