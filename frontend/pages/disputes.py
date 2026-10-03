from __future__ import annotations

import streamlit as st

from frontend.ui_helpers import get_receivables


st.title("Disputes")
st.caption("Invoices requiring dispute handling")

df = get_receivables()

if df.empty:
    st.info("No receivables data available.")
    st.stop()

disputes = df[
    ~df["dispute_status"]
    .astype(str)
    .str.lower()
    .isin(["", "none", "nan"])
].copy()

st.metric(
    "Open Disputes",
    len(disputes),
)

if disputes.empty:
    st.success(
        "No active disputes detected."
    )
else:
    st.dataframe(
        disputes,
        use_container_width=True,
        hide_index=True,
    )
