from pathlib import Path

p = Path(r".\frontend\streamlit_app.py")
s = p.read_text(encoding="utf-8")

start_marker = "# =========================================================\n# ACTIVE DATA SOURCE\n# ========================================================="
end_marker = "if receivables.empty:"

start = s.find(start_marker)
end = s.find(end_marker)

if start == -1:
    raise SystemExit("ACTIVE DATA SOURCE block not found.")

if end == -1:
    raise SystemExit("receivables.empty marker not found.")

new_block = '''# =========================================================
# ACTIVE DATA SOURCE
# =========================================================

if "company_receivables" in st.session_state:

    receivables = (
        st.session_state[
            "company_receivables"
        ].copy()
    )

    source_name = st.session_state.get(
        "company_file_name",
        "Uploaded company data",
    )

    st.success(
        f"Dashboard data source: {source_name}"
    )

else:

    runtime_company_path = (
        BASE_DIR
        / "data"
        / "runtime"
        / "company_receivables.csv"
    )

    if runtime_company_path.exists():

        try:

            receivables = pd.read_csv(
                runtime_company_path,
                encoding="utf-8-sig",
            )

            receivables = normalize_uploaded_data(
                receivables
            )

            st.success(
                "Dashboard data source: uploaded company data"
            )

        except UnicodeDecodeError:

            try:

                receivables = pd.read_csv(
                    runtime_company_path,
                    encoding="cp1252",
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

        if not demo_path.exists():

            st.info(
                "Upload your company CSV or PDF invoice to begin."
            )

            st.stop()

        try:

            receivables = pd.read_csv(
                demo_path,
                encoding="utf-8-sig",
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


'''

s = s[:start] + new_block + s[end:]

p.write_text(
    s,
    encoding="utf-8",
)

print("Active data source block repaired.")
