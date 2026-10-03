from __future__ import annotations

import streamlit as st

from frontend.ui_helpers import get_receivables


st.title("Receivables")
st.caption("Invoice-level receivables management")

df = get_receivables()

if df.empty:
    st.info("No receivables data available.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Invoices", len(df))

with c2:
    st.metric(
        "Invoice Value",
        f"₹{df['invoice_amount'].sum():,.0f}",
    )

with c3:
    st.metric(
        "Outstanding",
        f"₹{df['outstanding_amount'].sum():,.0f}",
    )

with c4:
    st.metric(
        "Overdue",
        int((df["overdue_days"] > 0).sum()),
    )

st.divider()

search = st.text_input(
    "Search customer or invoice"
)

if search.strip():
    value = search.strip().lower()

    mask = (
        df["customer_name"]
        .astype(str)
        .str.lower()
        .str.contains(value, na=False)
        |
        df["invoice_id"]
        .astype(str)
        .str.lower()
        .str.contains(value, na=False)
    )

    df = df[mask]

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
)
