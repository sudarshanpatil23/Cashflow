from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="CashFlowAI - Communications",
    page_icon="Email",
    layout="wide",
)


st.title("Communications")

st.caption(
    "Email collection workspace - review, approve, and track customer payment emails."
)


# ------------------------------------------------------------
# LOAD RECEIVABLES
# ------------------------------------------------------------

receivables = st.session_state.get(
    "reconciled_receivables"
)

if receivables is None:
    receivables = st.session_state.get(
        "company_receivables"
    )

if receivables is None:
    st.info(
        "Upload company receivables data first."
    )
    st.stop()


receivables = receivables.copy()


if receivables.empty:
    st.info(
        "No receivables available for communication."
    )
    st.stop()


# ------------------------------------------------------------
# REQUIRED COLUMNS
# ------------------------------------------------------------

defaults = {
    "invoice_id": "",
    "customer_name": "Unknown Customer",
    "outstanding_amount": 0.0,
    "overdue_days": 0,
    "payment_status": "Unknown",
}


for column, default in defaults.items():

    if column not in receivables.columns:
        receivables[column] = default


receivables["outstanding_amount"] = pd.to_numeric(
    receivables["outstanding_amount"],
    errors="coerce",
).fillna(0.0)


receivables["overdue_days"] = pd.to_numeric(
    receivables["overdue_days"],
    errors="coerce",
).fillna(0).astype(int)


# ------------------------------------------------------------
# ONLY OUTSTANDING INVOICES
# ------------------------------------------------------------

active = receivables[
    receivables["outstanding_amount"] > 0
].copy()


if active.empty:

    st.success(
        "No outstanding invoices currently require collection communication."
    )

    st.stop()


# ------------------------------------------------------------
# CREATE COLLECTION EMAIL
# ------------------------------------------------------------

st.subheader("Create Collection Email")


selected_invoice = st.selectbox(
    "Select invoice",
    active["invoice_id"].astype(str).tolist(),
)


row = active[
    active["invoice_id"].astype(str)
    == str(selected_invoice)
].iloc[0]


customer_name = str(
    row.get(
        "customer_name",
        "Customer",
    )
)


outstanding = float(
    row.get(
        "outstanding_amount",
        0,
    )
)


overdue_days = int(
    row.get(
        "overdue_days",
        0,
    )
)


# ------------------------------------------------------------
# COLLECTION RECOMMENDATION
# ------------------------------------------------------------

if overdue_days <= 7:

    email_type = "Friendly payment reminder"

elif overdue_days <= 15:

    email_type = "Formal payment reminder"

elif overdue_days <= 30:

    email_type = "Overdue payment follow-up"

else:

    email_type = "Management escalation review"


# ------------------------------------------------------------
# EMAIL DRAFT
# ------------------------------------------------------------

default_subject = (
    f"Payment follow-up - Invoice {selected_invoice}"
)


default_body = f"""Dear {customer_name},

I hope you are doing well.

This is a follow-up regarding invoice {selected_invoice}, which currently has an outstanding balance of Rs. {outstanding:,.0f}.

Our records show that the invoice is {overdue_days} days overdue. Please let us know the expected payment date or contact us if there is any issue with the invoice.

Regards,
Accounts Receivable Team
"""


# ------------------------------------------------------------
# INVOICE SUMMARY
# ------------------------------------------------------------

col1, col2 = st.columns(2)


with col1:

    st.metric(
        "Outstanding",
        f"Rs. {outstanding:,.0f}",
    )

    st.metric(
        "Overdue",
        f"{overdue_days} days",
    )


with col2:

    st.metric(
        "Recommended Email Type",
        email_type,
    )


st.divider()


# ------------------------------------------------------------
# EMAIL FIELDS
# ------------------------------------------------------------

recipient = st.text_input(
    "Customer email",
    value="",
    placeholder="customer@company.com",
)


subject = st.text_input(
    "Subject",
    value=default_subject,
)


body = st.text_area(
    "Email body",
    value=default_body,
    height=280,
)


st.caption(
    "Human approval is required before an email can be sent. "
    "This demo does not send real customer emails."
)


# ------------------------------------------------------------
# SESSION EMAIL DRAFT STORAGE
# ------------------------------------------------------------

if "communication_drafts" not in st.session_state:

    st.session_state[
        "communication_drafts"
    ] = {}


draft_key = str(
    selected_invoice
)


# ------------------------------------------------------------
# SAVE DRAFT
# ------------------------------------------------------------

if st.button(
    "Save Draft",
    type="secondary",
):

    st.session_state[
        "communication_drafts"
    ][draft_key] = {

        "invoice_id":
            str(selected_invoice),

        "customer_name":
            customer_name,

        "recipient":
            recipient.strip(),

        "subject":
            subject,

        "body":
            body,

        "email_type":
            email_type,

        "status":
            "Draft",

        "updated_at":
            datetime.now().isoformat(
                timespec="seconds"
            ),
    }

    st.success(
        "Email draft saved."
    )


# ------------------------------------------------------------
# HUMAN APPROVAL
# ------------------------------------------------------------

st.subheader(
    "Human Approval"
)


approve = st.checkbox(
    "I reviewed the recipient, subject, and email body and approve this email."
)


if approve:

    if not recipient.strip():

        st.warning(
            "Add a customer email address before approval."
        )

    elif "@" not in recipient:

        st.warning(
            "Enter a valid customer email address before approval."
        )

    else:

        if st.button(
            "Approve Email"
        ):

            st.session_state[
                "communication_drafts"
            ][draft_key] = {

                "invoice_id":
                    str(selected_invoice),

                "customer_name":
                    customer_name,

                "recipient":
                    recipient.strip(),

                "subject":
                    subject,

                "body":
                    body,

                "email_type":
                    email_type,

                "status":
                    "Approved - ready to send",

                "approved_at":
                    datetime.now().isoformat(
                        timespec="seconds"
                    ),
            }

            st.success(
                "Email approved. It is ready for the configured email provider."
            )


# ------------------------------------------------------------
# EMAIL TIMELINE
# ------------------------------------------------------------

st.divider()

st.subheader(
    "Email Timeline"
)


drafts = st.session_state.get(
    "communication_drafts",
    {},
)


if drafts:

    timeline = pd.DataFrame(
        list(drafts.values())
    )

    display_columns = [

        c

        for c in [

            "invoice_id",

            "customer_name",

            "recipient",

            "email_type",

            "status",

            "updated_at",

            "approved_at",

        ]

        if c in timeline.columns

    ]

    st.dataframe(
        timeline[display_columns],
        use_container_width=True,
        hide_index=True,
    )

else:

    st.info(
        "No email drafts created in this session."
    )


# ------------------------------------------------------------
# IMPORTANT DEMO DISCLAIMER
# ------------------------------------------------------------

st.caption(
    "Historical/demo communication records are separate from this email workflow. "
    "No real customer message is claimed as sent unless an email provider is configured."
)