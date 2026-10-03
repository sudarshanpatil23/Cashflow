from __future__ import annotations

import streamlit as st


st.set_page_config(
    page_title="CashFlowAI",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.sidebar.title("CashFlowAI")
st.sidebar.caption("AI Receivables & Collection Assistant")
st.sidebar.divider()

pages = [
    st.Page(
        "streamlit_app.py",
        title="Dashboard",
        icon=":material/dashboard:",
        default=True,
    ),
    st.Page(
        "pages/invoices.py",
        title="Receivables",
        icon=":material/receipt_long:",
    ),
    st.Page(
        "pages/payments.py",
        title="Payments",
        icon=":material/payments:",
    ),
    st.Page(
        "pages/customers.py",
        title="Customers",
        icon=":material/group:",
    ),
    st.Page(
        "pages/actions.py",
        title="Collections",
        icon=":material/task_alt:",
    ),
    st.Page(
        "pages/dashboard.py",
        title="Analytics",
        icon=":material/analytics:",
    ),
    st.Page(
        "pages/communications.py",
        title="Communications",
        icon=":material/email:",
    ),
    st.Page(
        "pages/disputes.py",
        title="Disputes",
        icon=":material/gavel:",
    ),
    st.Page(
        "pages/upload_center.py",
        title="Upload Center",
        icon=":material/cloud_upload:",
    ),
    st.Page(
        "pages/audit.py",
        title="Audit Log",
        icon=":material/history:",
    ),
    st.Page(
        "pages/settings.py",
        title="Settings",
        icon=":material/settings:",
    ),
]

navigation = st.navigation(
    pages,
    position="sidebar",
)

navigation.run()