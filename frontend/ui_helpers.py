from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.services.reconciliation_service import build_receivables_report


BASE_DIR = Path(__file__).resolve().parents[1]


def get_receivables() -> pd.DataFrame:
    if "company_receivables" in __import__("streamlit").session_state:
        df = __import__("streamlit").session_state[
            "company_receivables"
        ].copy()
    else:
        runtime_path = (
            BASE_DIR
            / "data"
            / "runtime"
            / "company_receivables.csv"
        )

        if runtime_path.exists():
            df = pd.read_csv(
                runtime_path,
                encoding="utf-8-sig",
            )
        else:
            try:
                df = build_receivables_report()
            except Exception:
                return pd.DataFrame()

    df.columns = [
        str(column).strip().lower()
        for column in df.columns
    ]

    if "amount" in df.columns and "invoice_amount" not in df.columns:
        df = df.rename(
            columns={"amount": "invoice_amount"}
        )

    numeric_columns = [
        "invoice_amount",
        "paid_amount",
        "outstanding_amount",
        "overdue_days",
    ]

    for column in numeric_columns:
        if column not in df.columns:
            df[column] = 0.0

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        ).fillna(0)

    defaults = {
        "customer_name": "Unknown Customer",
        "invoice_id": "Unknown Invoice",
        "payment_status": "Unknown",
        "dispute_status": "None",
        "communication_status": "Unknown",
    }

    for column, default in defaults.items():
        if column not in df.columns:
            df[column] = default

    return df


def get_payments() -> pd.DataFrame:
    import streamlit as st

    if "company_payments" in st.session_state:
        df = st.session_state[
            "company_payments"
        ].copy()
    else:
        runtime_path = (
            BASE_DIR
            / "data"
            / "runtime"
            / "payments.csv"
        )

        if not runtime_path.exists():
            return pd.DataFrame()

        df = pd.read_csv(
            runtime_path,
            encoding="utf-8-sig",
        )

    df.columns = [
        str(column).strip().lower()
        for column in df.columns
    ]

    return df


def get_risk_table(
    df: pd.DataFrame,
) -> pd.DataFrame:

    rows = []

    for _, row in df.iterrows():

        score = 0
        reasons = []

        overdue_days = float(
            row.get("overdue_days", 0)
        )

        outstanding = float(
            row.get("outstanding_amount", 0)
        )

        payment_status = str(
            row.get("payment_status", "")
        ).lower()

        communication_status = str(
            row.get("communication_status", "")
        ).lower()

        if overdue_days >= 15:
            score += 30
            reasons.append("15+ days overdue")

        if overdue_days >= 30:
            score += 20
            reasons.append("30+ days overdue")

        if (
            payment_status
            in {
                "partial",
                "partially paid",
                "partially_paid",
            }
            and outstanding > 0
        ):
            score += 10
            reasons.append("Partial payment outstanding")

        if "no response" in communication_status:
            score += 15
            reasons.append("No customer response")

        if outstanding >= 500000:
            score += 15
            reasons.append("₹5L+ outstanding")

        score = min(score, 100)

        if score >= 70:
            risk_level = "HIGH"
        elif score >= 40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        rows.append(
            {
                "customer_name": row.get(
                    "customer_name",
                    "Unknown",
                ),
                "invoice_id": row.get(
                    "invoice_id",
                    "Unknown",
                ),
                "outstanding_amount": outstanding,
                "overdue_days": overdue_days,
                "risk_score": score,
                "risk_level": risk_level,
                "risk_reasons": (
                    "; ".join(reasons)
                    if reasons
                    else "No major risk signals"
                ),
            }
        )

    return pd.DataFrame(rows)


def get_communications() -> pd.DataFrame:
    runtime_path = (
        BASE_DIR
        / "data"
        / "runtime"
        / "communications.csv"
    )

    demo_path = (
        BASE_DIR
        / "data"
        / "demo"
        / "communications.csv"
    )

    path = (
        runtime_path
        if runtime_path.exists()
        else demo_path
    )

    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(
        path,
        encoding="utf-8-sig",
    )


def get_audit_events() -> pd.DataFrame:
    audit_path = (
        BASE_DIR
        / "data"
        / "audit"
        / "audit_log.json"
    )

    if not audit_path.exists():
        return pd.DataFrame()

    try:
        import json

        with open(
            audit_path,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if isinstance(data, list):
            return pd.DataFrame(data)

    except Exception:
        pass

    return pd.DataFrame()
# ============================================================
# SQLite-backed UI data
# ============================================================

from app.services.db_read_service import (
    get_receivables_from_db,
    get_payments_from_db,
    get_customers_from_db,
)


def get_receivables() -> pd.DataFrame:
    df = get_receivables_from_db()

    if df.empty:
        return df

    # Keep compatibility with the existing dashboard/pages.
    if "amount" in df.columns and "invoice_amount" not in df.columns:
        df["invoice_amount"] = df["amount"]

    if "last_communication_date" not in df.columns:
        df["last_communication_date"] = pd.NaT

    if "communication_status" not in df.columns:
        df["communication_status"] = "Not Available"

    if "dispute_status" not in df.columns:
        df["dispute_status"] = "No Dispute Data"

    if "notes" not in df.columns:
        df["notes"] = ""

    return df


def get_payments() -> pd.DataFrame:
    return get_payments_from_db()


def get_customers() -> pd.DataFrame:
    return get_customers_from_db()
def get_communications() -> pd.DataFrame:
    from app.services.db_read_service import get_communications_from_db

    return get_communications_from_db()
def get_communications() -> pd.DataFrame:
    from app.services.db_read_service import get_communications_from_db

    return get_communications_from_db()
