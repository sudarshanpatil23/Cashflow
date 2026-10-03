import streamlit as st
import pandas as pd
import altair as alt

from frontend.ui_helpers import get_receivables
from app.services.cash_exposure_service import build_cash_exposure


st.title("Analytics")

df = get_receivables()

if df.empty:
    st.info("No receivables data available.")
    st.stop()


# ============================================================
# RECEIVABLES AGING
# ============================================================

st.subheader("Receivables Aging")

df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")

today = pd.Timestamp.today().normalize()

df["days_overdue"] = (
    today - df["due_date"]
).dt.days.clip(lower=0)

aging = pd.Series({
    "Current": df.loc[
        df["days_overdue"] == 0,
        "outstanding_amount"
    ].sum(),

    "1–15 Days": df.loc[
        (df["days_overdue"] >= 1) &
        (df["days_overdue"] <= 15),
        "outstanding_amount"
    ].sum(),

    "16–30 Days": df.loc[
        (df["days_overdue"] >= 16) &
        (df["days_overdue"] <= 30),
        "outstanding_amount"
    ].sum(),

    "31+ Days": df.loc[
        df["days_overdue"] > 30,
        "outstanding_amount"
    ].sum(),
})

# Explicit business-friendly order for the chart.
aging_order = [
    "Current",
    "1–15 Days",
    "16–30 Days",
    "31+ Days",
]

aging_df = (
    aging.rename("amount")
    .reset_index()
    .rename(columns={"index": "aging_bucket"})
)

aging_df["aging_bucket"] = pd.Categorical(
    aging_df["aging_bucket"],
    categories=aging_order,
    ordered=True,
)

aging_df = aging_df.sort_values("aging_bucket")

aging_chart = (
    alt.Chart(aging_df)
    .mark_bar()
    .encode(
        x=alt.X(
            "aging_bucket:N",
            sort=aging_order,
            title=None,
        ),
        y=alt.Y(
            "amount:Q",
            title="Outstanding Amount (₹)",
        ),
        tooltip=[
            alt.Tooltip(
                "aging_bucket:N",
                title="Aging Bucket",
            ),
            alt.Tooltip(
                "amount:Q",
                title="Outstanding",
                format=",.0f",
            ),
        ],
    )
    .properties(
        height=400,
    )
)

st.altair_chart(
    aging_chart,
    use_container_width=True,
)


# ============================================================
# TOP OUTSTANDING CUSTOMERS
# ============================================================

st.subheader("Top Outstanding Customers")

top_customers = (
    df.groupby("customer_name")["outstanding_amount"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
)

st.bar_chart(top_customers)


# ============================================================
# CASH EXPOSURE RADAR
# ============================================================

st.divider()

st.header("🚨 Cash Exposure Radar")

st.caption(
    "Baseline scenario estimate showing which outstanding "
    "receivables could create near-term cash exposure."
)


col1, col2 = st.columns(2)

with col1:
    required_cash = st.number_input(
        "Required cash for horizon (₹)",
        min_value=0.0,
        value=1000000.0,
        step=100000.0,
    )

with col2:
    horizon_days = st.number_input(
        "Cash horizon (days)",
        min_value=1,
        max_value=365,
        value=30,
        step=1,
    )


# ============================================================
# BUILD EXPOSURE
# ============================================================

exposure_result = build_cash_exposure(
    receivables=df,
    required_cash=required_cash,
    horizon_days=horizon_days,
)


# ============================================================
# METRICS
# ============================================================

metric1, metric2, metric3, metric4 = st.columns(4)

metric1.metric(
    "Required Cash",
    f"₹{exposure_result['required_cash']:,.0f}",
)

metric2.metric(
    "Projected Collection",
    f"₹{exposure_result['projected_collection']:,.0f}",
)

metric3.metric(
    "Cash Gap",
    f"₹{exposure_result['cash_gap']:,.0f}",
)

metric4.metric(
    "Cash at Risk",
    f"₹{exposure_result['cash_at_risk']:,.0f}",
)

st.caption(
    f"Baseline coverage: "
    f"{exposure_result['coverage_pct']:.1f}%"
)


# ============================================================
# TOP CASH EXPOSURES
# ============================================================

exposures = exposure_result["exposures"]

if exposures.empty:

    st.success(
        "No outstanding receivables fall within "
        "the selected cash horizon."
    )

else:

    st.subheader("Top Cash Exposures")

    display_columns = [
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
        column
        for column in display_columns
        if column in exposures.columns
    ]

    display_df = exposures[available_columns].copy()

    display_df = display_df.rename(
        columns={
            "invoice_id": "Invoice",
            "customer_name": "Customer",
            "outstanding_amount": "Outstanding",
            "overdue_days": "Overdue Days",
            "collection_probability": "Baseline Probability",
            "expected_collection": "Expected Collection",
            "cash_at_risk": "Cash at Risk",
            "risk_level": "Risk",
            "exposure_reason": "Reason",
        }
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# PRIORITY ALERT
# ============================================================

st.subheader("What Needs Attention?")

if not exposures.empty:

    high_exposure = exposures[
        exposures["risk_level"] == "High"
    ].copy()

    if not high_exposure.empty:

        top = high_exposure.iloc[0]

        customer = top.get(
            "customer_name",
            "Unknown customer"
        )

        invoice = top.get(
            "invoice_id",
            "Unknown invoice"
        )

        cash_at_risk = float(
            top.get("cash_at_risk", 0)
        )

        overdue_days = int(
            top.get("overdue_days", 0)
        )

        reason = top.get(
            "exposure_reason",
            "High exposure"
        )

        st.warning(
            f"Priority receivable: {customer} "
            f"({invoice}) — approximately "
            f"₹{cash_at_risk:,.0f} baseline cash exposure. "
            f"{overdue_days} days overdue. "
            f"Reason: {reason}."
        )

    else:

        st.info(
            "No high-risk receivables were identified "
            "under the current baseline scenario."
        )


st.caption(
    "Collection probabilities are transparent baseline "
    "scenario assumptions, not validated prediction accuracy "
    "or guaranteed cash forecasts."
)

