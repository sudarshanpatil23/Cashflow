from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import select

from app.models.database import SessionLocal
from app.models.entities import Customer, Invoice, Payment


def get_receivables_from_db() -> pd.DataFrame:
    with SessionLocal() as session:
        invoices = session.execute(
            select(Invoice)
        ).scalars().all()

        customers = {
            c.id: c
            for c in session.execute(select(Customer)).scalars().all()
        }

        payments = session.execute(
            select(Payment)
        ).scalars().all()

    payment_rows = []
    for payment in payments:
        if payment.is_duplicate:
            continue

        payment_rows.append(
            {
                "invoice_id": payment.invoice_id,
                "payment_amount": float(payment.payment_amount or 0),
                "payment_date": payment.payment_date,
            }
        )

    payments_df = pd.DataFrame(payment_rows)

    if payments_df.empty:
        paid_by_invoice = {}
        last_payment_by_invoice = {}
    else:
        grouped = payments_df.groupby("invoice_id")

        paid_by_invoice = (
            grouped["payment_amount"]
            .sum()
            .to_dict()
        )

        last_payment_by_invoice = (
            grouped["payment_date"]
            .max()
            .to_dict()
        )

    rows = []
    today = date.today()

    for invoice in invoices:
        amount = float(invoice.amount or 0)
        paid_amount = float(
            paid_by_invoice.get(invoice.id, 0)
        )

        outstanding = max(amount - paid_amount, 0)

        if outstanding <= 0:
            status = "Paid"
            overdue_days = 0

        elif invoice.due_date and invoice.due_date < today:
            status = "Overdue"
            overdue_days = (today - invoice.due_date).days

        elif paid_amount > 0:
            status = "Partial"
            overdue_days = 0

        else:
            status = "Open"
            overdue_days = 0

        customer = customers.get(invoice.customer_id)

        rows.append(
            {
                "invoice_id": invoice.id,
                "customer_id": invoice.customer_id,
                "customer_name": customer.name if customer else "Unknown Customer",
                "invoice_date": invoice.invoice_date,
                "due_date": invoice.due_date,
                "amount": amount,
                "currency": invoice.currency,
                "paid_amount": paid_amount,
                "outstanding_amount": outstanding,
                "payment_status": status,
                "overdue_days": overdue_days,
                "last_payment_date": last_payment_by_invoice.get(invoice.id),
            }
        )

    return pd.DataFrame(rows)


def get_payments_from_db() -> pd.DataFrame:
    with SessionLocal() as session:
        payments = session.execute(
            select(Payment)
        ).scalars().all()

        customers = {
            c.id: c.name
            for c in session.execute(select(Customer)).scalars().all()
        }

    rows = []

    for payment in payments:
        rows.append(
            {
                "invoice_id": payment.invoice_id,
                "customer_name": customers.get(
                    payment.customer_id,
                    "Unknown Customer",
                ),
                "payment_date": payment.payment_date,
                "payment_amount": float(
                    payment.payment_amount or 0
                ),
                "is_duplicate": bool(payment.is_duplicate),
                "reference": payment.reference,
            }
        )

    return pd.DataFrame(rows)


def get_customers_from_db() -> pd.DataFrame:
    with SessionLocal() as session:
        customers = session.execute(
            select(Customer)
        ).scalars().all()

    rows = []

    for customer in customers:
        rows.append(
            {
                "customer_id": customer.id,
                "customer_name": customer.name,
                "email": customer.email,
                "phone": customer.phone,
                "status": customer.status,
            }
        )

    return pd.DataFrame(rows)


if __name__ == "__main__":
    receivables = get_receivables_from_db()
    payments = get_payments_from_db()
    customers = get_customers_from_db()

    print("=" * 55)
    print("CASHFLOWAI DATABASE READ TEST")
    print("=" * 55)

    print(f"Receivables: {len(receivables)}")
    print(f"Payments: {len(payments)}")
    print(f"Customers: {len(customers)}")

    print()
    print(receivables.head().to_string(index=False))

    print("=" * 55)
def get_communications_from_db():
    from app.models.database import SessionLocal
    from app.models.entities import Communication

    import pandas as pd

    db = SessionLocal()

    try:
        rows = (
            db.query(Communication)
            .order_by(Communication.sent_at.asc())
            .all()
        )

        data = []

        for row in rows:
            data.append(
                {
                    "communication_id": row.id,
                    "invoice_id": row.invoice_id,
                    "customer_id": row.customer_id,
                    "channel": row.channel,
                    "direction": row.direction,
                    "subject": row.subject,
                    "message": row.message,
                    "status": row.status,
                    "communication_date": row.sent_at,
                    "created_at": row.created_at,
                }
            )

        return pd.DataFrame(data)

    finally:
        db.close()
