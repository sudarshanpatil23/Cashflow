from pathlib import Path
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
COMMUNICATIONS_FILE = BASE_DIR / "data" / "demo" / "communications.csv"


def load_communications():
    """Load customer communication history."""
    df = pd.read_csv(COMMUNICATIONS_FILE)

    df["communication_date"] = pd.to_datetime(
        df["communication_date"],
        errors="coerce"
    )

    return df


def classify_dispute(message):
    """Identify the type of dispute from the customer message."""

    text = str(message).lower()

    if "po mismatch" in text or (
        "po" in text and "mismatch" in text
    ):
        return "po_mismatch"

    if "extension" in text or "extend" in text:
        return "payment_extension"

    if "invoice" in text and (
        "incorrect" in text
        or "error" in text
        or "wrong" in text
    ):
        return "invoice_error"

    return "general_dispute"


def build_dispute_analysis():
    """Detect and summarize customer disputes."""

    communications = load_communications()

    disputes = communications[
        communications["status"].astype(str).str.lower() == "dispute"
    ].copy()

    if disputes.empty:
        return pd.DataFrame(
            columns=[
                "customer_id",
                "invoice_id",
                "dispute_count",
                "issue_types",
                "latest_dispute_date",
                "latest_message",
            ]
        )

    disputes["issue_type"] = disputes["message"].apply(
        classify_dispute
    )

    disputes = disputes.sort_values("communication_date")

    summary = (
        disputes
        .groupby(["customer_id", "invoice_id"])
        .agg(
            dispute_count=("invoice_id", "count"),
            issue_types=("issue_type", lambda x: ", ".join(sorted(set(x)))),
            latest_dispute_date=("communication_date", "max"),
            latest_message=("message", "last"),
        )
        .reset_index()
    )

    return summary


if __name__ == "__main__":
    dispute_report = build_dispute_analysis()

    print("\nCashFlowAI Dispute Analysis")
    print("=" * 70)

    print(f"Total dispute records: {len(dispute_report)}")

    if not dispute_report.empty:
        print("\nDetected disputes:\n")

        print(
            dispute_report[
                [
                    "customer_id",
                    "invoice_id",
                    "dispute_count",
                    "issue_types",
                    "latest_dispute_date",
                    "latest_message",
                ]
            ].to_string(index=False)
        )
    else:
        print("\nNo disputes detected.")