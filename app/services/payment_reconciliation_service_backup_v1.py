from __future__ import annotations

import pandas as pd


def normalize_payment_data(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:

    df = dataframe.copy()

    df.columns = [
        str(column).strip().lower()
        for column in df.columns
    ]

    if "invoice_id" not in df.columns:
        df["invoice_id"] = ""

    if "customer_name" not in df.columns:
        df["customer_name"] = ""

    if "payment_date" not in df.columns:
        df["payment_date"] = ""

    if "payment_amount" not in df.columns:
        df["payment_amount"] = 0

    df["invoice_id"] = (
        df["invoice_id"]
        .astype(str)
        .str.strip()
    )

    df["customer_name"] = (
        df["customer_name"]
        .astype(str)
        .str.strip()
    )

    df["payment_date"] = (
        df["payment_date"]
        .astype(str)
        .str.strip()
    )

    df["payment_amount"] = pd.to_numeric(
        df["payment_amount"],
        errors="coerce",
    ).fillna(0)

    return df


def find_duplicate_payments(
    payments: pd.DataFrame,
) -> pd.DataFrame:

    df = normalize_payment_data(
        payments
    )

    duplicate_mask = df.duplicated(
        subset=[
            "invoice_id",
            "payment_date",
            "payment_amount",
        ],
        keep=False,
    )

    return df[
        duplicate_mask
    ].copy()


def remove_duplicate_payments(
    payments: pd.DataFrame,
) -> pd.DataFrame:

    df = normalize_payment_data(
        payments
    )

    return df.drop_duplicates(
        subset=[
            "invoice_id",
            "payment_date",
            "payment_amount",
        ],
        keep="first",
    ).copy()


def determine_payment_status(
    row: pd.Series,
) -> str:

    invoice_amount = float(
        row.get(
            "invoice_amount",
            0,
        )
    )

    paid_amount = float(
        row.get(
            "paid_amount",
            0,
        )
    )

    if paid_amount <= 0:
        return "Unpaid"

    if (
        invoice_amount > 0
        and paid_amount >= invoice_amount
    ):
        return "Paid"

    return "Partially Paid"


def reconcile_payments(
    invoices: pd.DataFrame,
    payments: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:

    invoice_df = invoices.copy()

    invoice_df.columns = [
        str(column).strip().lower()
        for column in invoice_df.columns
    ]

    payment_df = normalize_payment_data(
        payments
    )

    if "invoice_id" not in invoice_df.columns:
        raise ValueError(
            "Invoice data must contain invoice_id."
        )

    if "invoice_amount" not in invoice_df.columns:

        if "amount" in invoice_df.columns:
            invoice_df = invoice_df.rename(
                columns={
                    "amount": "invoice_amount"
                }
            )
        else:
            raise ValueError(
                "Invoice data must contain amount or invoice_amount."
            )

    invoice_df["invoice_amount"] = pd.to_numeric(
        invoice_df["invoice_amount"],
        errors="coerce",
    ).fillna(0)

    invoice_df["invoice_id"] = (
        invoice_df["invoice_id"]
        .astype(str)
        .str.strip()
    )

    # Remove previously calculated payment fields before
    # rebuilding reconciliation results.
    for derived_column in [
        "paid_amount",
        "outstanding_amount",
        "payment_status",
    ]:
        if derived_column in invoice_df.columns:
            invoice_df = invoice_df.drop(
                columns=[derived_column]
            )

    duplicate_payments = (
        find_duplicate_payments(
            payment_df
        )
    )

    clean_payments = (
        remove_duplicate_payments(
            payment_df
        )
    )

    payment_summary = (
        clean_payments
        .groupby(
            "invoice_id",
            as_index=False,
        )["payment_amount"]
        .sum()
        .rename(
            columns={
                "payment_amount": "paid_amount"
            }
        )
    )

    reconciled = invoice_df.merge(
        payment_summary,
        on="invoice_id",
        how="left",
    )

    reconciled["paid_amount"] = (
        reconciled["paid_amount"]
        .fillna(0)
    )

    reconciled["outstanding_amount"] = (
        reconciled["invoice_amount"]
        - reconciled["paid_amount"]
    ).clip(lower=0)

    reconciled["payment_status"] = (
        reconciled.apply(
            determine_payment_status,
            axis=1,
        )
    )

    known_invoice_ids = set(
        invoice_df["invoice_id"]
    )

    unmatched_payments = (
        clean_payments[
            ~clean_payments[
                "invoice_id"
            ].isin(known_invoice_ids)
        ].copy()
    )

    return (
        reconciled,
        unmatched_payments,
    )


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

    if not duplicates.empty:
        duplicates["is_duplicate"] = True

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

