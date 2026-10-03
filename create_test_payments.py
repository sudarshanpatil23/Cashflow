import pandas as pd

invoices = pd.read_csv(
    r".\data\demo\invoices.csv"
)

rows = []

# 1. Full payment for first invoice
row = invoices.iloc[0]
rows.append({
    "invoice_id": row["invoice_id"],
    "customer_name": row["customer_name"],
    "payment_date": "2026-09-10",
    "payment_amount": float(row["amount"]),
})

# 2. Partial payment for second invoice
row = invoices.iloc[1]
rows.append({
    "invoice_id": row["invoice_id"],
    "customer_name": row["customer_name"],
    "payment_date": "2026-09-11",
    "payment_amount": round(float(row["amount"]) * 0.40, 2),
})

# 3. Two partial payments for third invoice
row = invoices.iloc[2]
rows.append({
    "invoice_id": row["invoice_id"],
    "customer_name": row["customer_name"],
    "payment_date": "2026-09-12",
    "payment_amount": round(float(row["amount"]) * 0.30, 2),
})
rows.append({
    "invoice_id": row["invoice_id"],
    "customer_name": row["customer_name"],
    "payment_date": "2026-09-18",
    "payment_amount": round(float(row["amount"]) * 0.20, 2),
})

# 4. Duplicate payment for fourth invoice
row = invoices.iloc[3]
duplicate_amount = round(float(row["amount"]) * 0.25, 2)
rows.append({
    "invoice_id": row["invoice_id"],
    "customer_name": row["customer_name"],
    "payment_date": "2026-09-13",
    "payment_amount": duplicate_amount,
})
rows.append({
    "invoice_id": row["invoice_id"],
    "customer_name": row["customer_name"],
    "payment_date": "2026-09-13",
    "payment_amount": duplicate_amount,
})

# 5. Partial payment for fifth invoice
row = invoices.iloc[4]
rows.append({
    "invoice_id": row["invoice_id"],
    "customer_name": row["customer_name"],
    "payment_date": "2026-09-14",
    "payment_amount": round(float(row["amount"]) * 0.50, 2),
})

# 6. Intentionally unmatched payment
rows.append({
    "invoice_id": "INV-9999",
    "customer_name": "Unknown Customer",
    "payment_date": "2026-09-15",
    "payment_amount": 75000,
})

payments = pd.DataFrame(rows)

payments.to_csv(
    r".\data\demo\payments.csv",
    index=False,
)

print(payments.to_string(index=False))
print()
print("Payment test file rebuilt using real invoice IDs.")
