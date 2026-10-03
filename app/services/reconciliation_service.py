from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "demo"


def load_data():
    invoices = pd.read_csv(DATA_DIR / "invoices.csv")
    payments = pd.read_csv(DATA_DIR / "payments.csv")

    invoices["invoice_date"] = pd.to_datetime(invoices["invoice_date"])
    invoices["due_date"] = pd.to_datetime(invoices["due_date"])
    payments["payment_date"] = pd.to_datetime(payments["payment_date"])

    return invoices, payments


def reconcile_payments() -> pd.DataFrame:
    invoices, payments = load_data()

    # Total payments received against each invoice.
    payment_totals = (
        payments.groupby("invoice_id", as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "paid_amount"})
    )

    # Attach payments to invoices.
    result = invoices.merge(
        payment_totals,
        on="invoice_id",
        how="left",
    )

    # Invoices without payments have zero paid amount.
    result["paid_amount"] = result["paid_amount"].fillna(0)

    # Calculate outstanding balance.
    result["outstanding_amount"] = (
        result["amount"] - result["paid_amount"]
    )

    # Protect against floating-point noise.
    result["outstanding_amount"] = result[
        "outstanding_amount"
    ].round(2)

    # Determine payment status.
    result["payment_status"] = result.apply(
        calculate_payment_status,
        axis=1,
    )

    return result


def calculate_payment_status(row) -> str:
    invoice_amount = float(row["amount"])
    paid_amount = float(row["paid_amount"])

    if paid_amount <= 0:
        return "unpaid"

    if paid_amount >= invoice_amount:
        return "paid"

    return "partially_paid"


def calculate_overdue_days(
    invoice: pd.Series,
    as_of_date: pd.Timestamp | None = None,
) -> int:
    if as_of_date is None:
        as_of_date = pd.Timestamp.today().normalize()

    due_date = invoice["due_date"]

    # Fully paid invoices are not considered outstanding overdue invoices.
    if invoice["outstanding_amount"] <= 0:
        return 0

    days = (as_of_date - due_date).days

    return max(days, 0)


def build_receivables_report() -> pd.DataFrame:
    result = reconcile_payments()

    result["overdue_days"] = result.apply(
        calculate_overdue_days,
        axis=1,
    )

    result["overdue_15_plus"] = (
        result["overdue_days"] >= 15
    )

    result["overdue_30_plus"] = (
        result["overdue_days"] >= 30
    )

    return result


if __name__ == "__main__":
    report = build_receivables_report()

    print("\nCashFlowAI Receivables Report")
    print("=" * 70)

    print(
        f"Total invoices: {len(report)}"
    )

    print(
        f"Total invoiced: "
        f"₹{report['amount'].sum():,.2f}"
    )

    print(
        f"Total paid: "
        f"₹{report['paid_amount'].sum():,.2f}"
    )

    print(
        f"Total outstanding: "
        f"₹{report['outstanding_amount'].sum():,.2f}"
    )

    print(
        f"Unpaid invoices: "
        f"{(report['payment_status'] == 'unpaid').sum()}"
    )

    print(
        f"Partially paid invoices: "
        f"{(report['payment_status'] == 'partially_paid').sum()}"
    )

    print(
        f"15+ days overdue: "
        f"{report['overdue_15_plus'].sum()}"
    )

    print(
        f"30+ days overdue: "
        f"{report['overdue_30_plus'].sum()}"
    )

    print("\nSample receivables:")
    print(
        report[
            [
                "invoice_id",
                "customer_name",
                "amount",
                "paid_amount",
                "outstanding_amount",
                "payment_status",
                "overdue_days",
            ]
        ].head(10).to_string(index=False)
    )