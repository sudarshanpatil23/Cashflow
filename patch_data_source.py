from pathlib import Path
import re

p = Path(r".\frontend\streamlit_app.py")
s = p.read_text(encoding="utf-8")

pattern = r'''(?s)# =========================================================
# ACTIVE DATA SOURCE
# =========================================================.*?if receivables\.empty:\s*
'''

replacement = r'''# =========================================================
# ACTIVE DATA SOURCE
# =========================================================

if "company_receivables" in st.session_state:

    receivables = st.session_state[
        "company_receivables"
    ].copy()

    source_name = st.session_state.get(
        "company_file_name",
        "Uploaded company data",
    )

    st.success(
        f"Dashboard data source: {source_name}"
    )

else:

    demo_path = (
        BASE_DIR
        / "data"
        / "demo"
        / "invoices.csv"
    )

    if not demo_path.exists():

        st.info(
            "Upload your company CSV or PDF invoice to begin."
        )

        st.stop()

    try:

        receivables = pd.read_csv(
            demo_path
        )

        receivables.columns = [
            str(column).strip().lower()
            for column in receivables.columns
        ]

        if "amount" in receivables.columns:
            receivables = receivables.rename(
                columns={
                    "amount": "invoice_amount"
                }
            )

        receivables = normalize_uploaded_data(
            receivables
        )

        st.info(
            "No company file uploaded. Showing demo data."
        )

    except Exception as error:

        st.error(
            f"Unable to load demo receivables data: {error}"
        )

        st.stop()


if receivables.empty:

'''

new_s, count = re.subn(
    pattern,
    replacement,
    s,
    count=1,
)

if count != 1:
    raise SystemExit(
        "Could not find the ACTIVE DATA SOURCE block."
    )

p.write_text(
    new_s,
    encoding="utf-8",
)

print("Active data source fixed.")
