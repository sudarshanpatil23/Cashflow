from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from app.models.database import SessionLocal, init_db
from app.models.entities import Company, Customer, Invoice, Payment


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
RUNTIME_DIR = DATA_DIR / "runtime"

COMPANY_ID = "demo-company"


def stable_customer_id(customer_id: str | None, customer_name: str) -> str:
    if customer_id and str(customer_id).strip():
        return str(customer_id).strip()

    raw = customer_name.strip().lower().encode("utf-8")
    return "cust-" + hashlib.sha1(raw).hexdigest()[:12]


def parse_date(value):
    if pd.isna(value) or value is None or str(value).strip() == "":
        return None
    return pd.to_datetime(value).date()


def clean_number(value) -> float:
    if pd.isna(value):
        return 0.0

    text = str(value).replace(",", "").replace("₹", "").strip()

    if not text:
        return 0.0

    return float(text)


def find_company(session):
    company = session.get(Company, COMPANY_ID)

    if company is None:
        company = Company(
            id=COMPANY_ID,
            name="CashFlowAI Demo Company",
        )
        session.add(company)

    return company


def sync_invoices(session, company_path: Path):
    df = pd.read_csv(company_path)

    df.columns = [str(c).strip().lower() for c in df.columns]

    if "invoice_id" not in df.columns:
        raise ValueError("Company CSV must contain invoice_id")

    if "customer_name" not in df.columns:
        raise ValueError("Company CSV must contain customer_name")

    amount_col = "amount" if "amount" in df.columns else "invoice_amount"

    if amount_col not in df.columns:
        raise ValueError("Company CSV must contain amount or invoice_amount")

    if "customer_id" not in df.columns:
        df["customer_id"] = ""

    created_customers = 0
    created_invoices = 0
    updated_invoices = 0

    for _, row in df.iterrows():
        invoice_id = str(row["invoice_id"]).strip()
        customer_name = str(row["customer_name"]).strip()

        customer_id = stable_customer_id(
            row.get("customer_id"),
            customer_name,
        )

        customer = session.get(Customer, customer_id)

        if customer is None:
            customer = Customer(
                id=customer_id,
                company_id=COMPANY_ID,
                name=customer_name,
                status="active",
            )
            session.add(customer)
            created_customers += 1
        else:
            customer.name = customer_name

        invoice = session.get(Invoice, invoice_id)

        values = {
            "company_id": COMPANY_ID,
            "customer_id": customer_id,
            "invoice_date": parse_date(row.get("invoice_date")),
            "due_date": parse_date(row.get("due_date")),
            "amount": clean_number(row[amount_col]),
            "currency": str(row.get("currency", "INR") or "INR").strip(),
        }

        if invoice is None:
            invoice = Invoice(
                id=invoice_id,
                **values,
            )
            session.add(invoice)
            created_invoices += 1
        else:
            for key, value in values.items():
                setattr(invoice, key, value)
            updated_invoices += 1

    return {
        "customers_created": created_customers,
        "invoices_created": created_invoices,
        "invoices_updated": updated_invoices,
    }


def sync_payments(session, payment_path: Path):
    if not payment_path.exists():
        return {
            "payments_created": 0,
            "payments_skipped": 0,
        }

    df = pd.read_csv(payment_path)
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = {"invoice_id", "payment_date"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Payment CSV missing columns: {sorted(missing)}"
        )

    amount_col = (
        "payment_amount"
        if "payment_amount" in df.columns
        else "amount"
        if "amount" in df.columns
        else None
    )

    if amount_col is None:
        raise ValueError(
            "Payment CSV must contain payment_amount or amount"
        )

    df["_occurrence"] = (
        df.groupby(
            [
                df["invoice_id"].astype(str).str.strip(),
                df["payment_date"].astype(str).str.strip(),
                df[amount_col].astype(str).str.strip(),
            ],
            dropna=False,
        ).cumcount()
    )

    created = 0
    skipped = 0

    for _, row in df.iterrows():
        invoice_id = str(row["invoice_id"]).strip()

        invoice = session.get(Invoice, invoice_id)

        customer_id = invoice.customer_id if invoice else None

        payment_date = parse_date(row["payment_date"])
        amount = clean_number(row[amount_col])
        occurrence = int(row["_occurrence"])

        reference_source = (
            f"{invoice_id}|{payment_date}|{amount}|{occurrence}"
        )

        reference = (
            "csv-"
            + hashlib.sha1(reference_source.encode("utf-8")).hexdigest()
        )

        existing = session.execute(
            select(Payment).where(Payment.reference == reference)
        ).scalar_one_or_none()

        if existing is not None:
            skipped += 1
            continue

        payment = Payment(
            invoice_id=invoice_id if invoice else None,
            customer_id=customer_id,
            payment_date=payment_date,
            payment_amount=amount,
            reference=reference,
            is_duplicate=False,
        )

        session.add(payment)
        created += 1

    return {
        "payments_created": created,
        "payments_skipped": skipped,
    }


def sync_runtime_data():
    init_db()

    company_path = RUNTIME_DIR / "company_receivables.csv"
    payment_path = RUNTIME_DIR / "payments.csv"

    if not company_path.exists():
        raise FileNotFoundError(
            f"Company receivables file not found: {company_path}"
        )

    with SessionLocal() as session:
        find_company(session)

        invoice_result = sync_invoices(
            session,
            company_path,
        )

        payment_result = sync_payments(
            session,
            payment_path,
        )

        session.commit()

    return {
        **invoice_result,
        **payment_result,
    }


if __name__ == "__main__":
    result = sync_runtime_data()

    print("=" * 55)
    print("CASHFLOWAI DATABASE SYNC")
    print("=" * 55)

    for key, value in result.items():
        print(f"{key}: {value}")

    print("=" * 55)
    print("✓ Runtime data synced to SQLite")
