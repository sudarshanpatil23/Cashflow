
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

import pandas as pd


def collection_probability(overdue_days: int) -> float:
    """
    Transparent baseline scenario assumption.

    This is NOT a trained prediction model and must not be presented
    as guaranteed collection probability.
    """
    if overdue_days <= 0:
        return 0.85
    if overdue_days <= 15:
        return 0.65
    if overdue_days <= 30:
        return 0.50
    return 0.35


def build_cash_exposure(
    receivables: pd.DataFrame,
    required_cash: float,
    horizon_days: int = 30,
    as_of: date | None = None,
) -> dict:
    """
    Build a transparent baseline cash-exposure scenario.

    required_cash:
        Cash requirement/target for the selected horizon.

    horizon_days:
        Number of future days to consider.

    The result is a scenario estimate, not a guaranteed forecast.
    """
    if as_of is None:
        as_of = date.today()

    df = receivables.copy()

    if df.empty:
        return {
            "required_cash": float(required_cash),
            "projected_collection": 0.0,
            "cash_gap": max(float(required_cash), 0.0),
            "coverage_pct": 0.0,
            "total_outstanding": 0.0,
            "cash_at_risk": 0.0,
            "exposures": pd.DataFrame(),
        }

    # Normalize required columns.
    if "invoice_amount" not in df.columns and "amount" in df.columns:
        df["invoice_amount"] = df["amount"]

    if "outstanding_amount" not in df.columns:
        if "outstanding" in df.columns:
            df["outstanding_amount"] = df["outstanding"]
        else:
            df["outstanding_amount"] = df["invoice_amount"]

    if "due_date" not in df.columns:
        raise ValueError("Receivables data must contain a due_date column.")

    df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")
    df["invoice_amount"] = pd.to_numeric(
        df["invoice_amount"], errors="coerce"
    ).fillna(0.0)
    df["outstanding_amount"] = pd.to_numeric(
        df["outstanding_amount"], errors="coerce"
    ).fillna(0.0)

    df = df[df["outstanding_amount"] > 0].copy()

    horizon_end = as_of + timedelta(days=horizon_days)

    # Include overdue invoices and invoices due within the horizon.
    df = df[
        (df["due_date"].dt.date <= horizon_end)
        | (df["due_date"].dt.date < as_of)
    ].copy()

    if df.empty:
        return {
            "required_cash": float(required_cash),
            "projected_collection": 0.0,
            "cash_gap": max(float(required_cash), 0.0),
            "coverage_pct": 0.0,
            "total_outstanding": 0.0,
            "cash_at_risk": 0.0,
            "exposures": pd.DataFrame(),
        }

    df["overdue_days"] = (
        as_of - df["due_date"].dt.date
    ).apply(lambda x: max(x.days, 0))

    df["collection_probability"] = df["overdue_days"].apply(
        collection_probability
    )

    df["expected_collection"] = (
        df["outstanding_amount"] * df["collection_probability"]
    )

    df["cash_at_risk"] = (
        df["outstanding_amount"] - df["expected_collection"]
    ).clip(lower=0)

    def exposure_level(row) -> str:
        if row["cash_at_risk"] >= 500000 or row["overdue_days"] > 30:
            return "High"
        if row["cash_at_risk"] >= 100000 or row["overdue_days"] > 15:
            return "Medium"
        return "Low"

    def exposure_reason(row) -> str:
        reasons = []

        if row["overdue_days"] > 30:
            reasons.append("30+ days overdue")
        elif row["overdue_days"] > 15:
            reasons.append("15+ days overdue")
        elif row["overdue_days"] > 0:
            reasons.append("overdue")

        if row["cash_at_risk"] >= 500000:
            reasons.append("high cash exposure")
        elif row["cash_at_risk"] >= 100000:
            reasons.append("material cash exposure")

        if not reasons:
            reasons.append("near-term receivable")

        return " + ".join(reasons)

    df["risk_level"] = df.apply(exposure_level, axis=1)
    df["exposure_reason"] = df.apply(exposure_reason, axis=1)

    projected_collection = float(df["expected_collection"].sum())
    total_outstanding = float(df["outstanding_amount"].sum())
    cash_at_risk = float(df["cash_at_risk"].sum())

    cash_gap = max(float(required_cash) - projected_collection, 0.0)

    coverage_pct = (
        (projected_collection / float(required_cash)) * 100
        if required_cash > 0
        else 100.0
    )

    df = df.sort_values(
        ["cash_at_risk", "outstanding_amount"],
        ascending=[False, False],
    ).reset_index(drop=True)

    return {
        "required_cash": float(required_cash),
        "projected_collection": projected_collection,
        "cash_gap": cash_gap,
        "coverage_pct": min(coverage_pct, 100.0),
        "total_outstanding": total_outstanding,
        "cash_at_risk": cash_at_risk,
        "exposures": df,
    }


def simulate_delay(
    receivables: pd.DataFrame,
    required_cash: float,
    horizon_days: int,
    invoice_ids: Iterable[str],
    delay_days: int,
    as_of: date | None = None,
) -> dict:
    """
    Simulate selected invoices being collected later than expected.

    This is a scenario tool, not a prediction.
    """
    if as_of is None:
        as_of = date.today()

    baseline = build_cash_exposure(
        receivables=receivables,
        required_cash=required_cash,
        horizon_days=horizon_days,
        as_of=as_of,
    )

    selected_ids = {str(x) for x in invoice_ids}

    df = receivables.copy()

    if "invoice_amount" not in df.columns and "amount" in df.columns:
        df["invoice_amount"] = df["amount"]

    if "outstanding_amount" not in df.columns:
        if "outstanding" in df.columns:
            df["outstanding_amount"] = df["outstanding"]
        else:
            df["outstanding_amount"] = df["invoice_amount"]

    df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")

    if "invoice_id" not in df.columns:
        raise ValueError("Receivables data must contain invoice_id.")

    mask = df["invoice_id"].astype(str).isin(selected_ids)

    df.loc[mask, "due_date"] = (
        df.loc[mask, "due_date"]
        + pd.to_timedelta(delay_days, unit="D")
    )

    scenario = build_cash_exposure(
        receivables=df,
        required_cash=required_cash,
        horizon_days=horizon_days,
        as_of=as_of,
    )

    scenario["baseline"] = baseline
    scenario["simulated_delay_days"] = delay_days
    scenario["simulated_invoice_ids"] = list(selected_ids)

    scenario["additional_cash_gap"] = max(
        scenario["cash_gap"] - baseline["cash_gap"],
        0.0,
    )

    return scenario


if __name__ == "__main__":
    from app.services.db_read_service import get_receivables_from_db

    receivables = get_receivables_from_db()

    result = build_cash_exposure(
        receivables=receivables,
        required_cash=1_000_000,
        horizon_days=30,
    )

    print("\n=== CASH EXPOSURE RADAR ===")
    print(f"Required cash:       ₹{result['required_cash']:,.0f}")
    print(f"Projected collection: ₹{result['projected_collection']:,.0f}")
    print(f"Cash gap:             ₹{result['cash_gap']:,.0f}")
    print(f"Coverage:             {result['coverage_pct']:.1f}%")
    print(f"Outstanding:          ₹{result['total_outstanding']:,.0f}")
    print(f"Cash at risk:         ₹{result['cash_at_risk']:,.0f}")

    exposures = result["exposures"]

    if exposures.empty:
        print("\nNo receivables found in the selected horizon.")
    else:
        columns = [
            "invoice_id",
            "customer_name",
            "outstanding_amount",
            "overdue_days",
            "collection_probability",
            "expected_collection",
            "cash_at_risk",
            "risk_level",
            "exposure_reason",
        ]

        available_columns = [
            column for column in columns if column in exposures.columns
        ]

        print("\n=== TOP CASH EXPOSURES ===")
        print(
            exposures[available_columns]
            .head(10)
            .to_string(index=False)
        )
