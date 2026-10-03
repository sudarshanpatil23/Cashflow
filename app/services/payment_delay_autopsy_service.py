from __future__ import annotations

from datetime import date

import pandas as pd


def build_payment_delay_autopsy(
    receivables: pd.DataFrame,
    payments: pd.DataFrame,
    customer_name: str | None = None,
    invoice_id: str | None = None,
    as_of: date | None = None,
) -> dict:
    """
    Analyze payment-delay behavior for a customer or invoice.

    This is an explainable behavioral analysis based on available
    invoice and payment history. It is not a predictive credit model.
    """

    if as_of is None:
        as_of = date.today()

    invoices = receivables.copy()
    payment_df = payments.copy()

    # ------------------------------------------------------------
    # Normalize invoice columns
    # ------------------------------------------------------------

    invoices.columns = [
        str(column).strip().lower()
        for column in invoices.columns
    ]

    if "invoice_amount" not in invoices.columns:
        if "amount" in invoices.columns:
            invoices["invoice_amount"] = invoices["amount"]
        else:
            raise ValueError(
                "Receivables data must contain invoice_amount or amount."
            )

    if "outstanding_amount" not in invoices.columns:
        if "outstanding" in invoices.columns:
            invoices["outstanding_amount"] = invoices["outstanding"]
        else:
            invoices["outstanding_amount"] = invoices["invoice_amount"]

    invoices["invoice_id"] = (
        invoices["invoice_id"]
        .astype(str)
        .str.strip()
    )

    invoices["customer_name"] = (
        invoices["customer_name"]
        .astype(str)
        .str.strip()
    )

    invoices["invoice_date"] = pd.to_datetime(
        invoices["invoice_date"],
        errors="coerce",
    )

    invoices["due_date"] = pd.to_datetime(
        invoices["due_date"],
        errors="coerce",
    )

    invoices["invoice_amount"] = pd.to_numeric(
        invoices["invoice_amount"],
        errors="coerce",
    ).fillna(0)

    invoices["outstanding_amount"] = pd.to_numeric(
        invoices["outstanding_amount"],
        errors="coerce",
    ).fillna(0)

    # ------------------------------------------------------------
    # Normalize payments
    # ------------------------------------------------------------

    payment_df.columns = [
        str(column).strip().lower()
        for column in payment_df.columns
    ]

    if "invoice_id" not in payment_df.columns:
        payment_df["invoice_id"] = ""

    if "payment_date" not in payment_df.columns:
        payment_df["payment_date"] = ""

    if "payment_amount" not in payment_df.columns:
        payment_df["payment_amount"] = 0

    payment_df["invoice_id"] = (
        payment_df["invoice_id"]
        .astype(str)
        .str.strip()
    )

    payment_df["payment_date"] = pd.to_datetime(
        payment_df["payment_date"],
        errors="coerce",
    )

    payment_df["payment_amount"] = pd.to_numeric(
        payment_df["payment_amount"],
        errors="coerce",
    ).fillna(0)

    # Remove exact duplicate payment records.
    payment_df = payment_df.drop_duplicates(
        subset=[
            "invoice_id",
            "payment_date",
            "payment_amount",
        ],
        keep="first",
    )

    # ------------------------------------------------------------
    # Select target invoices
    # ------------------------------------------------------------

    target = invoices.copy()

    if invoice_id:
        target = target[
            target["invoice_id"] == str(invoice_id).strip()
        ].copy()

    elif customer_name:
        target = target[
            target["customer_name"].str.casefold()
            == str(customer_name).strip().casefold()
        ].copy()

    if target.empty:
        return {
            "status": "not_found",
            "message": "No matching invoice or customer found.",
            "summary": {},
            "invoice_history": pd.DataFrame(),
            "payment_history": pd.DataFrame(),
            "reasons": [],
        }

    # ------------------------------------------------------------
    # Build payment history
    # ------------------------------------------------------------

    target_invoice_ids = set(
        target["invoice_id"].astype(str)
    )

    history = payment_df[
        payment_df["invoice_id"].isin(target_invoice_ids)
    ].copy()

    # ------------------------------------------------------------
    # Calculate invoice-level behavior
    # ------------------------------------------------------------

    invoice_rows = []

    for _, invoice in target.iterrows():

        inv_id = str(invoice["invoice_id"])

        due_date = invoice["due_date"]

        inv_payments = history[
            history["invoice_id"] == inv_id
        ].copy()

        paid_amount = float(
            inv_payments["payment_amount"].sum()
        )

        outstanding = max(
            float(invoice["invoice_amount"]) - paid_amount,
            0.0,
        )

        if pd.isna(due_date):
            overdue_days = 0
        else:
            overdue_days = max(
                (pd.Timestamp(as_of) - due_date).days,
                0,
            )

        payment_dates = (
            inv_payments["payment_date"]
            .dropna()
            .sort_values()
        )

        first_payment_delay = None

        if not payment_dates.empty and not pd.isna(due_date):
            first_payment_delay = max(
                (payment_dates.iloc[0] - due_date).days,
                0,
            )

        final_payment_delay = None

        if (
            outstanding <= 0
            and not payment_dates.empty
            and not pd.isna(due_date)
        ):
            final_payment_delay = max(
                (payment_dates.iloc[-1] - due_date).days,
                0,
            )

        invoice_rows.append(
            {
                "invoice_id": inv_id,
                "customer_name": invoice["customer_name"],
                "invoice_amount": float(
                    invoice["invoice_amount"]
                ),
                "paid_amount": paid_amount,
                "outstanding_amount": outstanding,
                "due_date": due_date,
                "overdue_days": overdue_days,
                "payment_count": len(inv_payments),
                "first_payment_delay": first_payment_delay,
                "final_payment_delay": final_payment_delay,
            }
        )

    invoice_history = pd.DataFrame(invoice_rows)

    # ------------------------------------------------------------
    # Behavioral metrics
    # ------------------------------------------------------------

    completed = invoice_history[
        invoice_history["outstanding_amount"] <= 0
    ].copy()

    currently_overdue = invoice_history[
        invoice_history["overdue_days"] > 0
    ].copy()

    total_invoices = len(invoice_history)

    completed_invoices = len(completed)

    overdue_invoice_count = len(currently_overdue)

    average_delay = 0.0

    completed_delays = completed[
        completed["final_payment_delay"].notna()
    ]["final_payment_delay"]

    if not completed_delays.empty:
        average_delay = float(
            completed_delays.mean()
        )

    partial_payment_count = len(
        invoice_history[
            (
                invoice_history["paid_amount"] > 0
            )
            &
            (
                invoice_history["outstanding_amount"] > 0
            )
        ]
    )

    repeated_late_payment = (
        len(
            completed[
                completed["final_payment_delay"].fillna(0) > 0
            ]
        ) >= 2
    )

    # ------------------------------------------------------------
    # Explainable reasons
    # ------------------------------------------------------------

    reasons = []

    if overdue_invoice_count > 0:
        reasons.append(
            f"{overdue_invoice_count} invoice(s) are currently overdue."
        )

    if average_delay > 0:
        reasons.append(
            f"Average completed-invoice payment delay is "
            f"{average_delay:.1f} days."
        )

    if repeated_late_payment:
        reasons.append(
            "Historical data shows repeated late-payment behavior."
        )

    if partial_payment_count > 0:
        reasons.append(
            f"{partial_payment_count} invoice(s) show partial-payment behavior."
        )

    if not reasons:
        reasons.append(
            "No significant payment-delay pattern was identified "
            "from the available history."
        )

    # ------------------------------------------------------------
    # Determine behavioral pattern
    # ------------------------------------------------------------

    if repeated_late_payment and partial_payment_count > 0:
        pattern = "Recurring late + partial payment behavior"

    elif repeated_late_payment:
        pattern = "Recurring payment delay"

    elif partial_payment_count > 0:
        pattern = "Partial payment behavior"

    elif overdue_invoice_count > 0:
        pattern = "Current overdue exposure"

    else:
        pattern = "No significant delay pattern"

    # ------------------------------------------------------------
    # Current invoice/customer status
    # ------------------------------------------------------------

    current_outstanding = float(
        invoice_history["outstanding_amount"].sum()
    )

    current_overdue_days = int(
        invoice_history["overdue_days"].max()
    )

    return {
        "status": "success",
        "summary": {
            "customer_name": (
                customer_name
                if customer_name
                else target.iloc[0]["customer_name"]
            ),
            "invoice_count": total_invoices,
            "completed_invoices": completed_invoices,
            "overdue_invoice_count": overdue_invoice_count,
            "current_outstanding": current_outstanding,
            "max_overdue_days": current_overdue_days,
            "average_payment_delay_days": round(
                average_delay,
                1,
            ),
            "partial_payment_count": partial_payment_count,
            "pattern": pattern,
        },
        "invoice_history": invoice_history,
        "payment_history": history,
        "reasons": reasons,
    }


if __name__ == "__main__":

    from app.services.db_read_service import (
        get_payments_from_db,
        get_receivables_from_db,
    )

    receivables = get_receivables_from_db()
    payments = get_payments_from_db()

    result = build_payment_delay_autopsy(
        receivables=receivables,
        payments=payments,
        customer_name="ABC Industries Pvt Ltd",
    )

    print("\n" + "=" * 60)
    print("       PAYMENT DELAY AUTOPSY")
    print("=" * 60)

    if result["status"] != "success":
        print(result["message"])

    else:

        summary = result["summary"]

        print(
            f"\nCustomer: {summary['customer_name']}"
        )

        print(
            f"Invoices analyzed: "
            f"{summary['invoice_count']}"
        )

        print(
            f"Current outstanding: "
            f"₹{summary['current_outstanding']:,.0f}"
        )

        print(
            f"Maximum overdue days: "
            f"{summary['max_overdue_days']}"
        )

        print(
            f"Average completed payment delay: "
            f"{summary['average_payment_delay_days']} days"
        )

        print(
            f"Partial-payment invoices: "
            f"{summary['partial_payment_count']}"
        )

        print(
            f"Behavior pattern: "
            f"{summary['pattern']}"
        )

        print("\nWhy this pattern was identified:")

        for reason in result["reasons"]:
            print(f"- {reason}")
