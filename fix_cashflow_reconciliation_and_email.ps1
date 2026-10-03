$ErrorActionPreference = "Stop"

$root = "C:\Users\ADMIN\Desktop\Cashflow"

Write-Host "=========================================="
Write-Host " CashFlowAI - Applying Product Fixes"
Write-Host "=========================================="

# ------------------------------------------------------------
# 1. FIND PAYMENT RECONCILIATION SERVICE
# ------------------------------------------------------------

$service = Get-ChildItem -Path $root -Recurse -Filter "payment_reconciliation_service.py" -File |
    Select-Object -First 1 -ExpandProperty FullName

if (-not $service) {
    throw "payment_reconciliation_service.py was not found under $root"
}

Write-Host ""
Write-Host "Found reconciliation service:"
Write-Host $service

$backup = "$service.before_cashflow_fix.bak"

Copy-Item $service $backup -Force

Write-Host "Backup created:"
Write-Host $backup

# ------------------------------------------------------------
# 2. REPLACE RECONCILIATION FUNCTION
# ------------------------------------------------------------

$serviceText = Get-Content $service -Raw

$start = $serviceText.IndexOf("def build_reconciliation_report(")

if ($start -lt 0) {
    throw "build_reconciliation_report() was not found."
}

$rest = $serviceText.Substring($start + 1)

$nextMatch = [regex]::Match(
    $rest,
    "(?m)^def\s+\w+\s*\("
)

if ($nextMatch.Success) {
    $end = $start + 1 + $nextMatch.Index
}
else {
    $end = $serviceText.Length
}

$newFunction = @'
def build_reconciliation_report(
    receivables: pd.DataFrame,
    payments: pd.DataFrame,
) -> dict:
    """
    Reconcile payment transactions against invoices.

    Rules:
    - Unknown invoice IDs are unmatched.
    - Exact duplicate payment rows are excluded.
    - Accepted payment transactions are the source of truth.
    - Paid/outstanding values are recalculated from accepted payments.
    """

    invoices = receivables.copy()
    tx = payments.copy()

    invoices.columns = [
        str(c).strip().lower()
        for c in invoices.columns
    ]

    tx.columns = [
        str(c).strip().lower()
        for c in tx.columns
    ]

    if "invoice_id" not in invoices.columns:
        raise ValueError(
            "Receivables data must contain invoice_id"
        )

    if "invoice_amount" not in invoices.columns:

        if "amount" in invoices.columns:
            invoices["invoice_amount"] = invoices["amount"]

        else:
            raise ValueError(
                "Receivables data must contain invoice_amount"
            )

    if tx.empty:

        result = invoices.copy()

        result["invoice_amount"] = pd.to_numeric(
            result["invoice_amount"],
            errors="coerce"
        ).fillna(0.0)

        if "paid_amount" not in result.columns:
            result["paid_amount"] = 0.0

        result["paid_amount"] = pd.to_numeric(
            result["paid_amount"],
            errors="coerce"
        ).fillna(0.0)

        result["outstanding_amount"] = (
            result["invoice_amount"]
            - result["paid_amount"]
        ).clip(lower=0)

        return {
            "reconciled": result,
            "unmatched_payments": tx.copy(),
            "duplicate_payments": tx.copy(),
        }

    required_payment_columns = {
        "invoice_id",
        "payment_date",
        "payment_amount",
    }

    missing = required_payment_columns - set(tx.columns)

    if missing:
        raise ValueError(
            "Payment data is missing required columns: "
            + ", ".join(sorted(missing))
        )

    invoices["invoice_id"] = (
        invoices["invoice_id"]
        .astype(str)
        .str.strip()
    )

    tx["invoice_id"] = (
        tx["invoice_id"]
        .astype(str)
        .str.strip()
    )

    tx["payment_amount"] = pd.to_numeric(
        tx["payment_amount"],
        errors="coerce"
    ).fillna(0.0)

    known_invoice_ids = set(
        invoices["invoice_id"]
    )

    unmatched_mask = (
        ~tx["invoice_id"].isin(known_invoice_ids)
    )

    unmatched = tx.loc[
        unmatched_mask
    ].copy()

    matched = tx.loc[
        ~unmatched_mask
    ].copy()

    duplicate_keys = [
        "invoice_id",
        "customer_name",
        "payment_date",
        "payment_amount",
    ]

    duplicate_keys = [
        c for c in duplicate_keys
        if c in matched.columns
    ]

    duplicate_mask = matched.duplicated(
        subset=duplicate_keys,
        keep="first"
    )

    duplicates = matched.loc[
        duplicate_mask
    ].copy()

    accepted = matched.loc[
        ~duplicate_mask
    ].copy()

    paid_by_invoice = (
        accepted
        .groupby(
            "invoice_id",
            dropna=False
        )["payment_amount"]
        .sum()
    )

    result = invoices.copy()

    result["invoice_amount"] = pd.to_numeric(
        result["invoice_amount"],
        errors="coerce"
    ).fillna(0.0)

    result["paid_amount"] = (
        result["invoice_id"]
        .map(paid_by_invoice)
        .fillna(0.0)
    )

    result["outstanding_amount"] = (
        result["invoice_amount"]
        - result["paid_amount"]
    ).clip(lower=0)

    result["payment_status"] = "Unpaid"

    result.loc[
        result["paid_amount"] >= result["invoice_amount"],
        "payment_status"
    ] = "Paid"

    result.loc[
        (result["paid_amount"] > 0)
        & (
            result["paid_amount"]
            < result["invoice_amount"]
        ),
        "payment_status"
    ] = "Partially Paid"

    if "payment_date" in accepted.columns:

        accepted_dates = pd.to_datetime(
            accepted["payment_date"],
            errors="coerce"
        )

        accepted = accepted.copy()

        accepted["_payment_date_parsed"] = (
            accepted_dates
        )

        last_payment = (
            accepted
            .dropna(
                subset=["_payment_date_parsed"]
            )
            .groupby("invoice_id")[
                "_payment_date_parsed"
            ]
            .max()
        )

        if "last_payment_date" in result.columns:

            result["last_payment_date"] = (
                result["invoice_id"]
                .map(last_payment)
                .dt.strftime("%Y-%m-%d")
                .fillna("")
            )

    return {
        "reconciled": result,
        "unmatched_payments": unmatched,
        "duplicate_payments": duplicates,
    }

'@

$serviceText =
    $serviceText.Substring(0, $start) +
    $newFunction +
    $serviceText.Substring($end)

Set-Content `
    -Path $service `
    -Value $serviceText `
    -Encoding UTF8

Write-Host ""
Write-Host "Payment reconciliation fixed."

# ------------------------------------------------------------
# 3. COMMUNICATIONS = EMAIL WORKSPACE
# ------------------------------------------------------------

$pagesDir = Join-Path $root "frontend\pages"

if (-not (Test-Path $pagesDir)) {
    throw "Frontend pages directory was not found."
}

$communications =
    Join-Path $pagesDir "communications.py"

if (Test-Path $communications) {

    Copy-Item `
        $communications `
        "$communications.before_cashflow_fix.bak" `
        -Force
}

$communicationPage = @'
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="CashFlowAI — Communications",
    page_icon="📧",
    layout="wide",
)


st.title("Communications")

st.caption(
    "Email collection workspace — review, approve, and track customer payment emails."
)


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
    errors="coerce"
).fillna(0.0)


receivables["overdue_days"] = pd.to_numeric(
    receivables["overdue_days"],
    errors="coerce"
).fillna(0).astype(int)


active = receivables[
    receivables["outstanding_amount"] > 0
].copy()


if active.empty:

    st.success(
        "No outstanding invoices currently require collection communication."
    )

    st.stop()


st.subheader("Create Collection Email")


selected_invoice = st.selectbox(
    "Select invoice",
    active["invoice_id"]
    .astype(str)
    .tolist(),
)


row = active[
    active["invoice_id"].astype(str)
    == str(selected_invoice)
].iloc[0]


customer_name = str(
    row.get(
        "customer_name",
        "Customer"
    )
)


outstanding = float(
    row.get(
        "outstanding_amount",
        0
    )
)


overdue_days = int(
    row.get(
        "overdue_days",
        0
    )
)


if overdue_days <= 7:

    email_type = (
        "Friendly payment reminder"
    )

elif overdue_days <= 15:

    email_type = (
        "Formal payment reminder"
    )

elif overdue_days <= 30:

    email_type = (
        "Overdue payment follow-up"
    )

else:

    email_type = (
        "Management escalation review"
    )


default_subject = (
    f"Payment follow-up — Invoice "
    f"{selected_invoice}"
)


default_body = f"""Dear {customer_name},

I hope you are doing well.

This is a follow-up regarding invoice {selected_invoice}, which currently has an outstanding balance of ₹{outstanding:,.0f}.

Our records show that the invoice is {overdue_days} days overdue. Please let us know the expected payment date or contact us if there is any issue with the invoice.

Regards,
Accounts Receivable Team
"""


col1, col2 = st.columns(2)


with col1:

    st.metric(
        "Outstanding",
        f"₹{outstanding:,.0f}"
    )

    st.metric(
        "Overdue",
        f"{overdue_days} days"
    )


with col2:

    st.metric(
        "Recommended Email Type",
        email_type
    )


st.divider()


recipient = st.text_input(
    "Customer email",
    value="",
    placeholder="customer@company.com",
)


subject = st.text_input(
    "Subject",
    value=default_subject
)


body = st.text_area(
    "Email body",
    value=default_body,
    height=280
)


st.caption(
    "Human approval is required before an email can be sent. "
    "This demo does not send real customer emails."
)


if "communication_drafts" not in st.session_state:

    st.session_state[
        "communication_drafts"
    ] = {}


draft_key = str(
    selected_invoice
)


if st.button(
    "Save Draft",
    type="secondary"
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
                    "Approved — ready to send",

                "approved_at":
                    datetime.now().isoformat(
                        timespec="seconds"
                    ),
            }

            st.success(
                "Email approved. It is ready for the configured email provider."
            )


st.divider()


st.subheader(
    "Email Timeline"
)


drafts = st.session_state.get(
    "communication_drafts",
    {}
)


if drafts:

    timeline = pd.DataFrame(
        list(drafts.values())
    )

    display_columns = [

        c for c in [

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


st.caption(
    "Historical/demo communication records are separate from this email workflow. "
    "No real customer message is claimed as sent unless an email provider is configured."
)

'@

Set-Content `
    -Path $communications `
    -Value $communicationPage `
    -Encoding UTF8

Write-Host ""
Write-Host "Communications email workspace updated."

# ------------------------------------------------------------
# 4. CUSTOMER 360 WORDING
# ------------------------------------------------------------

$customers =
    Join-Path $pagesDir "customers.py"


if (Test-Path $customers) {

    Copy-Item `
        $customers `
        "$customers.before_cashflow_fix.bak" `
        -Force

    $customerText =
        Get-Content $customers -Raw

    $customerText =
        $customerText.Replace(
            '"Avg. Payment Delay"',
            '"Avg. Historical Payment Delay"'
        )

    Set-Content `
        -Path $customers `
        -Value $customerText `
        -Encoding UTF8

    Write-Host ""
    Write-Host "Customer 360 wording updated."
}

# ------------------------------------------------------------
# 5. AUDIT WORDING
# ------------------------------------------------------------

$audit =
    Join-Path $pagesDir "audit.py"


if (Test-Path $audit) {

    Copy-Item `
        $audit `
        "$audit.before_cashflow_fix.bak" `
        -Force

    $auditText =
        Get-Content $audit -Raw

    $auditText =
        $auditText.Replace(
            'st.title("Audit Log")',
            'st.title("Audit Log — Historical Workflow Events")'
        )

    $auditText =
        $auditText.Replace(
            'st.header("Audit Log")',
            'st.header("Audit Log — Historical Workflow Events")'
        )

    Set-Content `
        -Path $audit `
        -Value $auditText `
        -Encoding UTF8

    Write-Host ""
    Write-Host "Audit wording updated."
}

# ------------------------------------------------------------
# DONE
# ------------------------------------------------------------

Write-Host ""
Write-Host "=========================================="
Write-Host " CASHFLOWAI FIX COMPLETE"
Write-Host "=========================================="
Write-Host ""

Write-Host "Now restart Streamlit with:"
Write-Host ""

Write-Host 'python -m streamlit run ".\frontend\streamlit_app.py"'ss