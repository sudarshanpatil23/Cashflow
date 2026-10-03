from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.ui_helpers import get_receivables


st.title("Collections")
st.caption("Collection work queue based on the active company receivables dataset.")


def calculate_collection_risk(row: pd.Series) -> tuple[int, str, list[str]]:
    score = 0
    reasons: list[str] = []

    overdue_days = float(row.get("overdue_days", 0) or 0)
    outstanding = float(row.get("outstanding_amount", 0) or 0)

    payment_status = (
        str(row.get("payment_status", ""))
        .strip()
        .lower()
    )

    communication_status = (
        str(row.get("communication_status", ""))
        .strip()
        .lower()
    )

    if overdue_days >= 15:
        score += 30
        reasons.append("Invoice is overdue by 15+ days")

    if overdue_days >= 30:
        score += 20
        reasons.append("Invoice is overdue by 30+ days")

    if payment_status in {
        "partial",
        "partially paid",
        "partially_paid",
    } and outstanding > 0:
        score += 10
        reasons.append("Invoice has an outstanding partial payment")

    if "no response" in communication_status:
        score += 15
        reasons.append("Customer has not responded")

    if outstanding >= 500000:
        score += 15
        reasons.append("Outstanding amount is ₹5 lakh or more")

    score = min(score, 100)

    if score >= 70:
        level = "HIGH"
    elif score >= 40:
        level = "MEDIUM"
    else:
        level = "LOW"

    return score, level, reasons


def recommended_action(row: pd.Series) -> str:
    dispute = (
        str(row.get("dispute_status", ""))
        .strip()
        .lower()
    )

    if dispute not in {"", "none", "nan"}:
        return "Resolve dispute before escalation"

    overdue_days = float(row.get("overdue_days", 0) or 0)

    if overdue_days <= 7:
        return "Friendly payment reminder"

    if overdue_days <= 15:
        return "Formal payment reminder"

    if overdue_days <= 30:
        return "Escalation review"

    return "Management review"


receivables = get_receivables().copy()

if receivables.empty:
    st.info("No receivable records available.")
    st.stop()


required_defaults = {
    "invoice_id": "Unknown",
    "customer_name": "Unknown Customer",
    "invoice_amount": 0.0,
    "paid_amount": 0.0,
    "outstanding_amount": 0.0,
    "overdue_days": 0,
    "payment_status": "Unpaid",
    "communication_status": "",
    "dispute_status": "None",
}

for column, default in required_defaults.items():
    if column not in receivables.columns:
        receivables[column] = default

for column in [
    "invoice_amount",
    "paid_amount",
    "outstanding_amount",
    "overdue_days",
]:
    receivables[column] = pd.to_numeric(
        receivables[column],
        errors="coerce",
    ).fillna(0)


risk_rows = []

for _, row in receivables.iterrows():
    score, level, reasons = calculate_collection_risk(row)

    risk_rows.append(
        {
            "customer_name": row["customer_name"],
            "invoice_id": row["invoice_id"],
            "outstanding_amount": row["outstanding_amount"],
            "overdue_days": row["overdue_days"],
            "risk_score": score,
            "risk_level": level,
            "risk_reasons": (
                "; ".join(reasons)
                if reasons
                else "No major risk signals"
            ),
            "recommended_action": recommended_action(row),
        }
    )

risk_df = pd.DataFrame(risk_rows)

high_count = int((risk_df["risk_level"] == "HIGH").sum())
medium_count = int((risk_df["risk_level"] == "MEDIUM").sum())
collection_cases = int(len(risk_df))

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("High Risk", high_count)

with col2:
    st.metric("Medium Risk", medium_count)

with col3:
    st.metric("Collection Cases", collection_cases)


st.divider()

st.subheader("Collection Work Queue")

filter_col1, filter_col2 = st.columns(2)

with filter_col1:
    risk_filter = st.selectbox(
        "Risk Level",
        ["All", "HIGH", "MEDIUM", "LOW"],
    )

with filter_col2:
    overdue_filter = st.selectbox(
        "Overdue",
        ["All", "Overdue", "15+ Days", "30+ Days"],
    )


display_df = risk_df.copy()

if risk_filter != "All":
    display_df = display_df[
        display_df["risk_level"] == risk_filter
    ]

if overdue_filter == "Overdue":
    display_df = display_df[
        display_df["overdue_days"] > 0
    ]
elif overdue_filter == "15+ Days":
    display_df = display_df[
        display_df["overdue_days"] >= 15
    ]
elif overdue_filter == "30+ Days":
    display_df = display_df[
        display_df["overdue_days"] >= 30
    ]


display_df = display_df.sort_values(
    ["risk_score", "outstanding_amount"],
    ascending=[False, False],
)

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Risk levels are rule-based collection signals using overdue age, "
    "payment status, communication status, and outstanding balance. "
    "They are not a validated predictive credit model."
)
