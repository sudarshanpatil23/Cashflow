from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json


BASE_DIR = Path(__file__).resolve().parents[2]
AUDIT_DIR = BASE_DIR / "data" / "audit"
AUDIT_FILE = AUDIT_DIR / "audit_log.json"


def save_audit_event(
    customer_id: str,
    customer_name: str,
    invoice_id: str,
    recommended_action: str,
    risk_score: int,
    risk_level: str,
    approval_status: str,
    approval_comment: str,
    email_status: str,
    email_sent: bool,
) -> None:
    """
    Save a CashFlowAI workflow event to the audit log.

    The audit log records:
    - customer
    - invoice
    - risk assessment
    - recommended action
    - human approval decision
    - approval comment
    - email status
    - timestamp
    """

    AUDIT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    event = {
        "timestamp": datetime.now().isoformat(
            timespec="seconds"
        ),
        "customer_id": customer_id,
        "customer_name": customer_name,
        "invoice_id": invoice_id,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "recommended_action": recommended_action,
        "approval_status": approval_status,
        "approval_comment": approval_comment,
        "email_status": email_status,
        "email_sent": email_sent,
    }

    existing_events = []

    if AUDIT_FILE.exists():
        try:
            with open(
                AUDIT_FILE,
                "r",
                encoding="utf-8",
            ) as file:
                existing_events = json.load(file)

        except (
            json.JSONDecodeError,
            OSError,
        ):
            existing_events = []

    existing_events.append(event)

    with open(
        AUDIT_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            existing_events,
            file,
            indent=4,
        )

    print("\n✓ AUDIT EVENT SAVED")
    print(f"Audit file: {AUDIT_FILE}")