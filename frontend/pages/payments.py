from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.ui_helpers import (
    get_payments,
    get_receivables,
)

from app.services.payment_reconciliation_service import (
    build_reconciliation_report,
)


st.title("Payments")
st.caption("Payment reconciliation and exceptions")

invoices = get_receivables()
payments = get_payments()

if invoices.empty:
    st.info("Upload invoice data first.")
    st.stop()

if payments.empty:
    st.info("No payment data available.")
    st.stop()

try:
    result = build_reconciliation_report(
        invoices,
        payments,
    )

    reconciled = result["reconciled"]
    unmatched = result["unmatched_payments"]
    duplicates = result["duplicate_payments"]

    total_paid = pd.to_numeric(
        reconciled["paid_amount"],
        errors="coerce",
    ).fillna(0).sum()

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Payment Records",
            len(payments),
        )

    with c2:
        st.metric(
            "Total Paid",
            f"₹{total_paid:,.0f}",
        )

    with c3:
        st.metric(
            "Unmatched",
            len(unmatched),
        )

    with c4:
        st.metric(
            "Duplicates",
            len(duplicates),
        )

    st.subheader("Reconciled Invoices")

    st.dataframe(
        reconciled[
            [
                "invoice_id",
                "invoice_amount",
                "paid_amount",
                "outstanding_amount",
                "payment_status",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    if not unmatched.empty:
        st.subheader("Unmatched Payments")
        st.dataframe(
            unmatched,
            use_container_width=True,
            hide_index=True,
        )

    if not duplicates.empty:
        st.subheader("Duplicate Payments")
        st.dataframe(
            duplicates,
            use_container_width=True,
            hide_index=True,
        )

except Exception as error:
    st.error(
        f"Payment reconciliation failed: {error}"
    )
