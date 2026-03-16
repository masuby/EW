"""Audit logging for bulletin generation events."""

import json
import logging
from datetime import datetime
from pathlib import Path

AUDIT_LOG_DIR = Path(__file__).parent.parent / "output" / "audit"
AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)

_logger = logging.getLogger("ew_audit")
if not _logger.handlers:
    _handler = logging.FileHandler(AUDIT_LOG_DIR / "audit.log")
    _handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)


def log_generation(username: str, role: str, bulletin_type: str,
                   json_data: dict, result: dict, duration: float):
    """Log a bulletin generation event."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "username": username,
        "role": role,
        "bulletin_type": bulletin_type,
        "issue_date": json_data.get("issue_date"),
        "duration_seconds": round(duration, 2),
        "success": result.get("error") is None,
        "output_files": {
            k: v for k, v in (result.get("result") or {}).items()
        },
    }
    _logger.info(json.dumps(entry, ensure_ascii=False))


def get_audit_entries(limit: int = 50) -> list[dict]:
    """Read recent audit log entries."""
    log_file = AUDIT_LOG_DIR / "audit.log"
    if not log_file.exists():
        return []
    lines = log_file.read_text().strip().split("\n")
    entries = []
    for line in lines[-limit:]:
        try:
            json_part = line.split(" | ", 1)[1]
            entries.append(json.loads(json_part))
        except (IndexError, json.JSONDecodeError):
            continue
    return list(reversed(entries))
