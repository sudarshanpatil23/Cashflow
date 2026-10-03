from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parents[2]

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.models.database import SessionLocal, init_db
from app.models.entities import (
    AuditLog,
    CollectionAction,
    Customer,
    Invoice,
    Payment,
    PaymentPromise,
)
from app.services.db_sync_service import COMPANY_ID


st.set_page_config(
    page_title="Promise to Pay | CashFlowAI",
    page_icon="💰",
    layout="wide",
)

st.title("Promise-to-Pay Workspace")
st.caption(
    "Track customer payment commitments, identify broken promises, "
    "and create controlled collection follow-up actions."
)


# ============================================================
# DATABASE
# ============================================================

init_db()


def load_data():
    with SessionLocal() as db:

        customers = (
            db.query(Customer)
            .filter(Customer.company_id == COMPANY_ID)
            .all()
        )

        invoices = (
            db.query(Invoice)
            .filter(Invoice.company_id == COMPANY_ID)
            .all()
        )

        invoice_ids = [
            invoice.id
            for invoice in invoices
        ]

        if invoice_ids:
            payments = (
                db.query(Payment)
                .filter(
                    Payment.invoice_id.in_(invoice_ids)
                )
                .all()
            )
        else:
            payments = []

        promises = (
            db.query(PaymentPromise)
            .filter(
                PaymentPromise.company_id == COMPANY_ID
            )
            .order_by(
                PaymentPromise.created_at.desc()
            )
            .all()
        )

        return (
            customers,
            invoices,
            payments,
            promises,
        )


# ============================================================
# PAYMENT CALCULATION
# ============================================================

def calculate_paid_amount(
    invoice_id,
    payment_records,
):
    total = 0.0
    seen = set()

    for payment in payment_records:

        if payment.invoice_id != invoice_id:
            continue

        if bool(payment.is_duplicate):
            continue

        key = (
            payment.invoice_id,
            payment.payment_date,
            float(payment.payment_amount or 0),
        )

        if key in seen:
            continue

        seen.add(key)

        total += float(
            payment.payment_amount or 0
        )

    return total


def calculate_outstanding(
    invoice,
    payment_records,
):
    paid = calculate_paid_amount(
        invoice.id,
        payment_records,
    )

    return max(
        float(invoice.amount or 0) - paid,
        0.0,
    )


# ============================================================
# REFRESH PROMISE STATUS
# ============================================================

def refresh_promise_status():

    with SessionLocal() as db:

        db_invoices = (
            db.query(Invoice)
            .filter(
                Invoice.company_id == COMPANY_ID
            )
            .all()
        )

        invoice_map_db = {
            invoice.id: invoice
            for invoice in db_invoices
        }

        invoice_ids = list(
            invoice_map_db.keys()
        )

        if invoice_ids:
            db_payments = (
                db.query(Payment)
                .filter(
                    Payment.invoice_id.in_(invoice_ids)
                )
                .all()
            )
        else:
            db_payments = []

        db_promises = (
            db.query(PaymentPromise)
            .filter(
                PaymentPromise.company_id == COMPANY_ID
            )
            .all()
        )

        changed = False

        for promise in db_promises:

            invoice = invoice_map_db.get(
                promise.invoice_id
            )

            if invoice is None:
                continue

            promised_amount = float(
                promise.promised_amount or 0
            )

            paid_amount = calculate_paid_amount(
                promise.invoice_id,
                db_payments,
            )

            old_status = promise.status

            # ------------------------------------------------
            # PAYMENT-AWARE STATUS
            # ------------------------------------------------

            if paid_amount >= promised_amount:
                new_status = "fulfilled"

            elif paid_amount > 0:
                new_status = "partial"

            elif (
                promise.promised_date is not None
                and promise.promised_date < date.today()
                and promise.status != "cancelled"
            ):
                new_status = "broken"

            else:
                new_status = "pending"

            # ------------------------------------------------
            # STATUS CHANGE
            # ------------------------------------------------

            if old_status != new_status:

                promise.status = new_status
                changed = True

                db.add(
                    AuditLog(
                        company_id=COMPANY_ID,
                        action="Payment promise status changed",
                        entity_type="payment_promise",
                        entity_id=str(promise.id),
                        details=(
                            f"Invoice {promise.invoice_id}; "
                            f"paid Rs. {paid_amount:,.2f} "
                            f"of promised Rs. "
                            f"{promised_amount:,.2f}; "
                            f"status changed from "
                            f"{old_status} to {new_status}."
                        ),
                    )
                )

                if new_status == "broken":

                    db.add(
                        CollectionAction(
                            company_id=COMPANY_ID,
                            customer_id=promise.customer_id,
                            invoice_id=promise.invoice_id,
                            action_type="Broken Promise Follow-up",
                            priority="high",
                            reason=(
                                "Customer payment promise "
                                "date has passed and the "
                                "promised amount has not "
                                "been received."
                            ),
                            status="pending",
                        )
                    )

        if changed:
            db.commit()


# ============================================================
# INITIAL LOAD + STATUS REFRESH
# ============================================================

refresh_promise_status()

customers, invoices, payments, promises = load_data()

customer_map = {
    customer.id: customer
    for customer in customers
}

invoice_map = {
    invoice.id: invoice
    for invoice in invoices
}


# ============================================================
# METRICS
# ============================================================

pending_count = sum(
    promise.status == "pending"
    for promise in promises
)

partial_count = sum(
    promise.status == "partial"
    for promise in promises
)

fulfilled_count = sum(
    promise.status == "fulfilled"
    for promise in promises
)

broken_count = sum(
    promise.status == "broken"
    for promise in promises
)

total_promised = sum(
    float(promise.promised_amount or 0)
    for promise in promises
)


m1, m2, m3, m4, m5 = st.columns(5)

with m1:
    st.metric(
        "Total Promises",
        len(promises),
    )

with m2:
    st.metric(
        "Pending",
        pending_count,
    )

with m3:
    st.metric(
        "Partial",
        partial_count,
    )

with m4:
    st.metric(
        "Fulfilled",
        fulfilled_count,
    )

with m5:
    st.metric(
        "Broken",
        broken_count,
    )


if broken_count > 0:
    st.error(
        f"{broken_count} broken payment promise(s) "
        "require collection follow-up."
    )


# ============================================================
# RECORD PROMISE
# ============================================================

st.divider()

st.subheader("Record Customer Promise")


outstanding_invoices = []

for invoice in invoices:

    outstanding = calculate_outstanding(
        invoice,
        payments,
    )

    if outstanding <= 0:
        continue

    customer = customer_map.get(
        invoice.customer_id
    )

    overdue_days = 0

    if invoice.due_date:
        overdue_days = max(
            (date.today() - invoice.due_date).days,
            0,
        )

    outstanding_invoices.append(
        {
            "invoice": invoice,
            "customer": customer,
            "outstanding": outstanding,
            "overdue_days": overdue_days,
        }
    )


if not outstanding_invoices:

    st.info(
        "No outstanding invoices are available "
        "for a new payment promise."
    )

else:

    options = {}

    for row in outstanding_invoices:

        invoice = row["invoice"]
        customer = row["customer"]

        customer_name = (
            customer.name
            if customer
            else "Unknown Customer"
        )

        label = (
            f"{invoice.id} | "
            f"{customer_name} | "
            f"Rs. {row['outstanding']:,.0f}"
        )

        options[label] = row

    with st.form("record_payment_promise"):

        selected_label = st.selectbox(
            "Invoice",
            list(options.keys()),
        )

        selected = options[
            selected_label
        ]

        invoice = selected["invoice"]
        customer = selected["customer"]

        c1, c2 = st.columns(2)

        with c1:
            st.text_input(
                "Customer",
                value=(
                    customer.name
                    if customer
                    else "Unknown Customer"
                ),
                disabled=True,
            )

        with c2:
            st.text_input(
                "Current Outstanding",
                value=(
                    f"Rs. "
                    f"{selected['outstanding']:,.2f}"
                ),
                disabled=True,
            )

        promised_amount = st.number_input(
            "Promised Payment Amount",
            min_value=0.01,
            max_value=float(
                selected["outstanding"]
            ),
            value=float(
                min(
                    selected["outstanding"],
                    10000.0,
                )
            ),
            step=1000.0,
        )

        promised_date = st.date_input(
            "Promised Payment Date",
            value=date.today(),
        )

        submitted = st.form_submit_button(
            "Record Promise",
            type="primary",
            use_container_width=True,
        )

        if submitted:

            with SessionLocal() as db:

                promise = PaymentPromise(
                    company_id=COMPANY_ID,
                    customer_id=(
                        customer.id
                        if customer
                        else None
                    ),
                    invoice_id=invoice.id,
                    promised_date=promised_date,
                    promised_amount=promised_amount,
                    status="pending",
                )

                db.add(promise)

                db.flush()

                priority = (
                    "high"
                    if selected["overdue_days"] > 30
                    else "medium"
                )

                db.add(
                    CollectionAction(
                        company_id=COMPANY_ID,
                        customer_id=(
                            customer.id
                            if customer
                            else None
                        ),
                        invoice_id=invoice.id,
                        action_type="Promise-to-Pay Tracking",
                        priority=priority,
                        reason=(
                            f"Customer promised "
                            f"Rs. {promised_amount:,.2f} "
                            f"by "
                            f"{promised_date.isoformat()}."
                        ),
                        status="pending",
                    )
                )

                db.add(
                    AuditLog(
                        company_id=COMPANY_ID,
                        action="Payment promise recorded",
                        entity_type="payment_promise",
                        entity_id=str(promise.id),
                        details=(
                            f"Invoice {invoice.id}; "
                            f"promised amount "
                            f"Rs. {promised_amount:,.2f}; "
                            f"promised date "
                            f"{promised_date.isoformat()}."
                        ),
                    )
                )

                db.commit()

            st.success(
                "Payment promise recorded successfully."
            )

            st.rerun()


# ============================================================
# PROMISE TRACKING
# ============================================================

st.divider()

st.subheader("Promise Tracking")


if not promises:

    st.info(
        "No payment promises have been recorded yet."
    )

else:

    rows = []

    for promise in promises:

        customer = customer_map.get(
            promise.customer_id
        )

        invoice = invoice_map.get(
            promise.invoice_id
        )

        paid_against_invoice = (
            calculate_paid_amount(
                promise.invoice_id,
                payments,
            )
        )

        promised_amount = float(
            promise.promised_amount or 0
        )

        rows.append(
            {
                "Promise ID": promise.id,
                "Invoice": (
                    promise.invoice_id
                    or "-"
                ),
                "Customer": (
                    customer.name
                    if customer
                    else "Unknown Customer"
                ),
                "Promised Amount": (
                    f"Rs. {promised_amount:,.0f}"
                ),
                "Paid on Invoice": (
                    f"Rs. {paid_against_invoice:,.0f}"
                ),
                "Promised Date": (
                    promise.promised_date
                    or "-"
                ),
                "Status": str(
                    promise.status
                ).upper(),
                "Created": (
                    promise.created_at.strftime(
                        "%Y-%m-%d %H:%M"
                    )
                    if promise.created_at
                    else "-"
                ),
            }
        )

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# BROKEN PROMISE ANALYSIS
# ============================================================

st.divider()

st.subheader("Broken Promise Analysis")


broken_promises = [
    promise
    for promise in promises
    if promise.status == "broken"
]


if not broken_promises:

    st.success(
        "No broken payment promises currently "
        "require follow-up."
    )

else:

    broken_rows = []

    for promise in broken_promises:

        customer = customer_map.get(
            promise.customer_id
        )

        invoice = invoice_map.get(
            promise.invoice_id
        )

        outstanding = (
            calculate_outstanding(
                invoice,
                payments,
            )
            if invoice
            else 0.0
        )

        paid_amount = calculate_paid_amount(
            promise.invoice_id,
            payments,
        )

        promised_amount = float(
            promise.promised_amount or 0
        )

        broken_rows.append(
            {
                "Customer": (
                    customer.name
                    if customer
                    else "Unknown Customer"
                ),
                "Invoice": (
                    promise.invoice_id
                    or "-"
                ),
                "Promised": (
                    f"Rs. {promised_amount:,.0f}"
                ),
                "Paid": (
                    f"Rs. {paid_amount:,.0f}"
                ),
                "Promise Date": (
                    promise.promised_date
                    or "-"
                ),
                "Still Outstanding": (
                    f"Rs. {outstanding:,.0f}"
                ),
                "Status": "BROKEN",
                "Recommended Follow-up": (
                    "Collector review and "
                    "customer follow-up"
                ),
            }
        )

    st.dataframe(
        pd.DataFrame(broken_rows),
        use_container_width=True,
        hide_index=True,
    )


st.caption(
    "Promise status is an operational workflow signal, "
    "not a predictive payment model."
)