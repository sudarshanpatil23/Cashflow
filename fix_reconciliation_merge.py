from pathlib import Path

p = Path(r".\app\services\payment_reconciliation_service.py")
s = p.read_text(encoding="utf-8")

old = '''    invoice_df["invoice_amount"] = pd.to_numeric(
        invoice_df["invoice_amount"],
        errors="coerce",
    ).fillna(0)

    invoice_df["invoice_id"] = (
        invoice_df["invoice_id"]
        .astype(str)
        .str.strip()
    )
'''

new = '''    invoice_df["invoice_amount"] = pd.to_numeric(
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
'''

if old not in s:
    raise SystemExit(
        "Expected reconciliation block was not found."
    )

s = s.replace(
    old,
    new,
    1,
)

p.write_text(
    s,
    encoding="utf-8",
)

print("Reconciliation engine fixed.")
