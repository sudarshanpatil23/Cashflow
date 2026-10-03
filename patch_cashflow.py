from pathlib import Path

p = Path(r".\frontend\streamlit_app.py")
s = p.read_text(encoding="utf-8")

# 1. Persist uploaded company data to disk
old_company = '''            st.session_state[
                "company_receivables"
            ] = uploaded_data

            st.session_state[
                "company_file_name"
            ] = uploaded_file.name
'''

new_company = '''            st.session_state[
                "company_receivables"
            ] = uploaded_data.copy()

            st.session_state[
                "company_file_name"
            ] = uploaded_file.name

            runtime_dir = BASE_DIR / "data" / "runtime"
            runtime_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            uploaded_data.to_csv(
                runtime_dir / "company_receivables.csv",
                index=False,
            )
'''

if old_company in s:
    s = s.replace(old_company, new_company, 1)

# 2. Persist uploaded payment data to disk
old_payment = '''            st.session_state[
                "company_payments"
            ] = payment_data

            st.session_state[
                "payment_file_name"
            ] = payment_file.name
'''

new_payment = '''            st.session_state[
                "company_payments"
            ] = payment_data.copy()

            st.session_state[
                "payment_file_name"
            ] = payment_file.name

            runtime_dir = BASE_DIR / "data" / "runtime"
            runtime_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            payment_data.to_csv(
                runtime_dir / "payments.csv",
                index=False,
            )
'''

if old_payment in s:
    s = s.replace(old_payment, new_payment, 1)

# 3. Restore persisted company data before falling back to demo data
old_source = '''else:

    demo_path = (
        BASE_DIR
        / "data"
        / "demo"
        / "invoices.csv"
    )
'''

new_source = '''else:

    runtime_company_path = (
        BASE_DIR
        / "data"
        / "runtime"
        / "company_receivables.csv"
    )

    if runtime_company_path.exists():

        try:
            receivables = pd.read_csv(
                runtime_company_path
            )

            receivables = normalize_uploaded_data(
                receivables
            )

            st.success(
                "Dashboard data source: uploaded company data"
            )

        except Exception as error:

            st.error(
                f"Unable to load saved company data: {error}"
            )

            st.stop()

    else:

        demo_path = (
            BASE_DIR
            / "data"
            / "demo"
            / "invoices.csv"
        )
'''

if old_source in s:
    s = s.replace(old_source, new_source, 1)

# 4. Guarantee reconciliation-required columns
marker = '''# =========================================================
# PAYMENT RECONCILIATION
# =========================================================
'''

insert = '''# =========================================================
# RECONCILIATION INPUT NORMALIZATION
# =========================================================

if "paid_amount" not in receivables.columns:
    receivables["paid_amount"] = 0.0

if "payment_status" not in receivables.columns:
    receivables["payment_status"] = "Unpaid"

if "invoice_amount" not in receivables.columns:
    if "amount" in receivables.columns:
        receivables = receivables.rename(
            columns={"amount": "invoice_amount"}
        )
    else:
        receivables["invoice_amount"] = 0.0


# =========================================================
# PAYMENT RECONCILIATION
# =========================================================
'''

if marker in s:
    s = s.replace(marker, insert, 1)

p.write_text(
    s,
    encoding="utf-8",
)

print("CashFlowAI upload/reconciliation persistence fixed.")
