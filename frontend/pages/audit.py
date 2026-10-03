from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parents[2]

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.models.database import SessionLocal, init_db
from app.models.entities import AuditLog
from app.services.db_sync_service import COMPANY_ID


st.title("Audit Log - Historical Workflow Events")
st.caption("System and collection activity")

init_db()


with SessionLocal() as db:

    events = (
        db.query(AuditLog)
        .filter(
            AuditLog.company_id == COMPANY_ID
        )
        .order_by(
            AuditLog.created_at.desc()
        )
        .all()
    )


if events:

    rows = []

    for event in events:
        rows.append(
            {
                "Event ID": event.id,
                "Action": event.action,
                "Entity Type": event.entity_type or "-",
                "Entity ID": event.entity_id or "-",
                "Details": event.details or "-",
                "Created": (
                    event.created_at.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    if event.created_at
                    else "-"
                ),
            }
        )

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        f"{len(events)} workflow event(s) "
        "recorded for the active company."
    )

else:

    st.info(
        "No audit events available yet."
    )
