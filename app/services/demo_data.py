from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import random

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "demo"

random.seed(42)


CUSTOMERS = [
    ("CUST001", "ABC Industries", "abc@example.com"),
    ("CUST002", "Nova Retail", "finance@nova.example.com"),
    ("CUST003", "Shree Enterprises", "accounts@shree.example.com"),
    ("CUST004", "Bright Manufacturing", "payables@bright.example.com"),
    ("CUST005", "Vertex Solutions", "finance@vertex.example.com"),
    ("CUST006", "Pioneer Distributors", "accounts@pioneer.example.com"),
    ("CUST007", "BlueStone Traders", "finance@bluestone.example.com"),
    ("CUST008", "Sunrise Components", "payables@sunrise.example.com"),
    ("CUST009", "Metro Engineering", "accounts@metro.example.com"),
    ("CUST010", "GreenField Foods", "finance@greenfield.example.com"),
    ("CUST011", "Apex Systems", "accounts@apex.example.com"),
    ("CUST012", "Omkar Trading", "payables@omkar.example.com"),
    ("CUST013", "Silverline Exports", "finance@silverline.example.com"),
    ("CUST014", "Prime Packaging", "accounts@prime.example.com"),
    ("CUST015", "Urban BuildTech", "finance@urbanbuild.example.com"),
    ("CUST016", "Delta Components", "payables@delta.example.com"),
    ("CUST017", "Reliable Machines", "accounts@reliable.example.com"),
    ("CUST018", "NextGen Electronics", "finance@nextgen.example.com"),
    ("CUST019", "Everest Supplies", "accounts@everest.example.com"),
    ("CUST020", "Maharashtra TechWorks", "finance@mhtechworks.example.com"),
]


def generate_customers() -> pd.DataFrame:
    rows = []

    for customer_id, name, email in CUSTOMERS:
        rows.append(
            {
                "customer_id": customer_id,
                "customer_name": name,
                "email": email,
                "payment_terms_days": random.choice([15, 30, 45]),
            }
        )

    return pd.DataFrame(rows)


def generate_invoices() -> pd.DataFrame:
    today = date.today()
    rows = []

    for i in range(1, 101):
        customer_id, customer_name, _ = random.choice(CUSTOMERS)

        issue_date = today - timedelta(
            days=random.randint(5, 100)
        )

        customer_terms = random.choice([15, 30, 45])

        due_date = issue_date + timedelta(
            days=customer_terms
        )

        amount = random.choice(
            [
                25000,
                45000,
                75000,
                100000,
                150000,
                250000,
                400000,
                500000,
                750000,
                1000000,
            ]
        )

        rows.append(
            {
                "invoice_id": f"INV{i:03d}",
                "customer_id": customer_id,
                "customer_name": customer_name,
                "invoice_date": issue_date.isoformat(),
                "due_date": due_date.isoformat(),
                "amount": amount,
                "currency": "INR",
            }
        )

    return pd.DataFrame(rows)


def generate_payments(
    invoices: pd.DataFrame,
) -> pd.DataFrame:

    rows = []
    payment_counter = 1
    today = date.today()

    for _, invoice in invoices.iterrows():

        amount = float(invoice["amount"])

        scenario = random.choices(
            ["unpaid", "partial", "paid"],
            weights=[35, 30, 35],
            k=1,
        )[0]

        if scenario == "unpaid":
            continue

        if scenario == "paid":
            payment_amount = amount
        else:
            payment_amount = round(
                amount
                * random.choice(
                    [0.25, 0.40, 0.50, 0.60, 0.75]
                ),
                2,
            )

        invoice_date = date.fromisoformat(
            invoice["invoice_date"]
        )

        # Payment cannot happen in the future.
        max_payment_days = max(
            1,
            (today - invoice_date).days,
        )

        payment_date = invoice_date + timedelta(
            days=random.randint(
                1,
                max_payment_days,
            )
        )

        rows.append(
            {
                "payment_id": f"PAY{payment_counter:03d}",
                "invoice_id": invoice["invoice_id"],
                "customer_id": invoice["customer_id"],
                "payment_date": payment_date.isoformat(),
                "amount": payment_amount,
                "reference": f"UTR-DEMO-{payment_counter:05d}",
            }
        )

        payment_counter += 1

    return pd.DataFrame(rows)


def generate_communications(
    invoices: pd.DataFrame,
) -> pd.DataFrame:

    rows = []

    communication_counter = 1
    today = date.today()

    templates = [
        (
            "email",
            "sent",
            "Payment reminder sent to customer.",
        ),
        (
            "email",
            "no_response",
            "Payment reminder sent. No response received.",
        ),
        (
            "email",
            "response",
            "Customer responded regarding payment.",
        ),
        (
            "email",
            "response",
            "Customer requested payment extension.",
        ),
        (
            "email",
            "dispute",
            "Customer reported PO mismatch on invoice.",
        ),
    ]

    for _, invoice in invoices.iterrows():

        number_of_messages = random.randint(0, 4)

        invoice_date = date.fromisoformat(
            invoice["invoice_date"]
        )

        max_communication_days = max(
            1,
            (today - invoice_date).days,
        )

        for _ in range(number_of_messages):

            channel, status, message = random.choice(
                templates
            )

            # Communication cannot happen before the invoice
            # and cannot happen in the future.
            communication_date = invoice_date + timedelta(
                days=random.randint(
                    1,
                    max_communication_days,
                )
            )

            rows.append(
                {
                    "communication_id": (
                        f"COM{communication_counter:03d}"
                    ),
                    "invoice_id": invoice["invoice_id"],
                    "customer_id": invoice["customer_id"],
                    "communication_date": (
                        communication_date.isoformat()
                    ),
                    "channel": channel,
                    "status": status,
                    "message": message,
                }
            )

            communication_counter += 1

    return pd.DataFrame(rows)


def generate_demo_data() -> None:

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    customers = generate_customers()
    invoices = generate_invoices()
    payments = generate_payments(invoices)
    communications = generate_communications(
        invoices
    )

    customers.to_csv(
        DATA_DIR / "customers.csv",
        index=False,
    )

    invoices.to_csv(
        DATA_DIR / "invoices.csv",
        index=False,
    )

    payments.to_csv(
        DATA_DIR / "payments.csv",
        index=False,
    )

    communications.to_csv(
        DATA_DIR / "communications.csv",
        index=False,
    )

    print(
        "CashFlowAI demo data generated successfully."
    )

    print(f"Customers: {len(customers)}")
    print(f"Invoices: {len(invoices)}")
    print(f"Payments: {len(payments)}")
    print(
        f"Communications: {len(communications)}"
    )


if __name__ == "__main__":
    generate_demo_data()