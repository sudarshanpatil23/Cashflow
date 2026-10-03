from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.services.reconciliation_service import build_receivables_report
from app.services.dispute_service import build_dispute_analysis


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "demo"


def load_communications() -> pd.DataFrame:
    communications = pd.read_csv(
        DATA_DIR / "communications.csv"
    )

    communications["communication_date"] = pd.to_datetime(
        communications["communication_date"]
    )

    return communications


def build_customer_analysis() -> pd.DataFrame:
    receivables = build_receivables_report()

    customer_summary = (
        receivables
        .groupby(
            [
                "customer_id",
                "customer_name",
            ],
            as_index=False,
        )
        .agg(
            total_invoiced=("amount", "sum"),
            total_paid=("paid_amount", "sum"),
            outstanding_amount=("outstanding_amount", "sum"),
            total_invoices=("invoice_id", "count"),
            unpaid_invoices=(
                "payment_status",
                lambda x: (x == "unpaid").sum(),
            ),
            partially_paid_invoices=(
                "payment_status",
                lambda x: (x == "partially_paid").sum(),
            ),
            overdue_15_plus=(
                "overdue_15_plus",
                "sum",
            ),
            overdue_30_plus=(
                "overdue_30_plus",
                "sum",
            ),
            maximum_overdue_days=(
                "overdue_days",
                "max",
            ),
        )
    )

    customer_summary["collection_status"] = (
        customer_summary.apply(
            determine_collection_status,
            axis=1,
        )
    )

    return customer_summary


def determine_collection_status(row) -> str:
    if row["overdue_30_plus"] > 0:
        return "management_review"

    if row["overdue_15_plus"] > 0:
        return "escalation_review"

    if row["unpaid_invoices"] > 0:
        return "follow_up"

    if row["partially_paid_invoices"] > 0:
        return "monitor"

    return "current"


def add_communication_analysis(
    customer_summary: pd.DataFrame,
) -> pd.DataFrame:

    communications = load_communications()

    communication_summary = (
        communications
        .groupby("customer_id", as_index=False)
        .agg(
            total_communications=(
                "communication_id",
                "count",
            ),
            no_response_count=(
                "status",
                lambda x: (x == "no_response").sum(),
            ),
            response_count=(
                "status",
                lambda x: (x == "response").sum(),
            ),
            dispute_count=(
                "status",
                lambda x: (x == "dispute").sum(),
            ),
            last_communication_date=(
                "communication_date",
                "max",
            ),
        )
    )

    # Get detailed dispute information
    dispute_analysis = build_dispute_analysis()

    if not dispute_analysis.empty:

        dispute_summary = (
            dispute_analysis
            .groupby("customer_id", as_index=False)
            .agg(
                dispute_types=(
                    "issue_types",
                    lambda x: ", ".join(
                        sorted(
                            set(
                                ", ".join(x).split(", ")
                            )
                        )
                    ),
                ),
                latest_dispute_date=(
                    "latest_dispute_date",
                    "max",
                ),
            )
        )

        communication_summary = communication_summary.merge(
            dispute_summary,
            on="customer_id",
            how="left",
        )

    result = customer_summary.merge(
        communication_summary,
        on="customer_id",
        how="left",
    )

    numeric_columns = [
        "total_communications",
        "no_response_count",
        "response_count",
        "dispute_count",
    ]

    for column in numeric_columns:
        result[column] = result[column].fillna(0)

    if "dispute_types" not in result.columns:
        result["dispute_types"] = "none"
    else:
        result["dispute_types"] = (
            result["dispute_types"].fillna("none")
        )

    return result


if __name__ == "__main__":

    customers = build_customer_analysis()

    customers = add_communication_analysis(
        customers
    )

    print("\nCashFlowAI Customer Analysis")
    print("=" * 80)

    print(
        customers[
            [
                "customer_name",
                "outstanding_amount",
                "unpaid_invoices",
                "partially_paid_invoices",
                "overdue_15_plus",
                "overdue_30_plus",
                "no_response_count",
                "dispute_count",
                "dispute_types",
                "collection_status",
            ]
        ]
        .sort_values(
            "outstanding_amount",
            ascending=False,
        )
        .head(10)
        .to_string(index=False)
    )