import pandas as pd

from app.services.payment_reconciliation_service import (
    build_reconciliation_report,
)

invoices = pd.read_csv(
    r".\data\demo\invoices.csv"
).rename(
    columns={"amount": "invoice_amount"}
)

payments = pd.read_csv(
    r".\data\demo\payments.csv"
)

result = build_reconciliation_report(
    invoices,
    payments,
)

print("\n===== RECONCILED INVOICES =====\n")

print(
    result["reconciled"][
        [
            "invoice_id",
            "invoice_amount",
            "paid_amount",
            "outstanding_amount",
            "payment_status",
        ]
    ].to_string(index=False)
)

print("\n===== UNMATCHED PAYMENTS =====\n")

if result["unmatched_payments"].empty:
    print("None")
else:
    print(
        result["unmatched_payments"][
            [
                "invoice_id",
                "customer_name",
                "payment_amount",
            ]
        ].to_string(index=False)
    )

print("\n===== DUPLICATE PAYMENTS =====\n")

if result["duplicate_payments"].empty:
    print("None")
else:
    print(
        result["duplicate_payments"][
            [
                "invoice_id",
                "customer_name",
                "payment_amount",
            ]
        ].to_string(index=False)
    )
