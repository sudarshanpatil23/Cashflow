from __future__ import annotations

import pandas as pd

from app.services.customer_service import (
    add_communication_analysis,
    build_customer_analysis,
)


def calculate_risk(row) -> tuple[int, list[str]]:
    score = 0
    reasons = []

    # 15+ days overdue
    if row["overdue_15_plus"] > 0:
        score += 30
        reasons.append(
            f"{int(row['overdue_15_plus'])} invoice(s) are 15+ days overdue"
        )

    # 30+ days overdue
    if row["overdue_30_plus"] > 0:
        score += 20
        reasons.append(
            f"{int(row['overdue_30_plus'])} invoice(s) are 30+ days overdue"
        )

    # Repeated unpaid/partially-paid invoices
    repeated_problem_invoices = (
        row["unpaid_invoices"]
        + row["partially_paid_invoices"]
    )

    if repeated_problem_invoices >= 3:
        score += 20
        reasons.append(
            f"{int(repeated_problem_invoices)} invoice(s) require payment attention"
        )

    # No response
    if row["no_response_count"] > 0:
        score += 15
        reasons.append(
            f"{int(row['no_response_count'])} communication(s) received no response"
        )

    # Large outstanding balance
    if row["outstanding_amount"] >= 500000:
        score += 15
        reasons.append(
            f"₹{row['outstanding_amount']:,.0f} is currently outstanding"
        )

    # Cap the score at 100.
    score = min(score, 100)

    return score, reasons


def classify_risk(score: int) -> str:
    if score >= 70:
        return "HIGH"

    if score >= 40:
        return "MEDIUM"

    return "LOW"


def build_risk_analysis() -> pd.DataFrame:
    customers = build_customer_analysis()
    customers = add_communication_analysis(customers)

    risk_results = customers.apply(
        calculate_risk,
        axis=1,
        result_type="expand",
    )

    risk_results.columns = [
        "risk_score",
        "risk_reasons",
    ]

    customers["risk_score"] = risk_results["risk_score"]
    customers["risk_reasons"] = risk_results["risk_reasons"]

    customers["risk_level"] = customers[
        "risk_score"
    ].apply(classify_risk)

    return customers


if __name__ == "__main__":

    result = build_risk_analysis()

    print("\nCashFlowAI Risk Analysis")
    print("=" * 100)

    display_columns = [
        "customer_name",
        "outstanding_amount",
        "overdue_15_plus",
        "overdue_30_plus",
        "no_response_count",
        "risk_score",
        "risk_level",
        "risk_reasons",
    ]

    print(
        result[
            display_columns
        ]
        .sort_values(
            "risk_score",
            ascending=False,
        )
        .head(10)
        .to_string(index=False)
    )