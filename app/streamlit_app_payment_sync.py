from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parents[1]

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.services.file_processor import (
    get_file_info,
    read_tabular_file,
    save_uploaded_file,
)
from app.services.invoice_pdf_service import extract_invoice_fields
from app.services.reconciliation_service import build_receivables_report
from app.services.payment_reconciliation_service import build_reconciliation_report
from app.models.database import SessionLocal, init_db
from app.models.entities import (
    CollectionAction,
    Communication,
    Customer,
    Dispute,
    Invoice,
    Payment,
    PaymentPromise,
)
from app.services.db_sync_service import sync_runtime_data


st.set_page_config(
    page_title="CashFlowAI",
    page_icon="💰",
    layout="wide",
)

st.title("CashFlowAI")
st.caption(
    "AI Receivables & Collection Assistant for Indian MSMEs"
)


# =========================================================
# HELPERS
# =========================================================

def normalize_uploaded_data(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:

    df = dataframe.copy()

    df.columns = [
        str(column).strip().lower()
        for column in df.columns
    ]

    # Common business CSV column names.
    aliases = {
        "invoice_number": "invoice_id",
        "invoice_no": "invoice_id",
        "customer": "customer_name",
        "customer_name": "customer_name",
        "invoice_value": "invoice_amount",
        "total_amount": "invoice_amount",
        "invoice_amount": "invoice_amount",
    }

    rename_map = {}

    for old_name, new_name in aliases.items():

        if (
            old_name in df.columns
            and new_name not in df.columns
        ):
            rename_map[old_name] = new_name

    if rename_map:
        df = df.rename(columns=rename_map)

    # Map amount -> invoice_amount when required.
    if (
        "invoice_amount" not in df.columns
        and "amount" in df.columns
    ):
        df["invoice_amount"] = df["amount"]

    if "invoice_amount" not in df.columns:
        df["invoice_amount"] = 0.0

    # Database sync uses the canonical `amount` field.
    if "amount" not in df.columns:
        df["amount"] = df["invoice_amount"]

    if "paid_amount" not in df.columns:
        df["paid_amount"] = 0.0

    # Numeric fields.
    for column in [
        "invoice_amount",
        "paid_amount",
        "outstanding_amount",
        "overdue_days",
    ]:

        if column not in df.columns:
            df[column] = 0.0

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        ).fillna(0.0)

    # Calculate outstanding amount when the CSV does not provide it.
    if "outstanding_amount" not in dataframe.columns.str.lower().tolist():
        df["outstanding_amount"] = (
            df["invoice_amount"]
            - df["paid_amount"]
        ).clip(lower=0)

    # Basic identifiers.
    if "payment_status" not in df.columns:
        df["payment_status"] = "Unknown"

    if "customer_name" not in df.columns:
        df["customer_name"] = "Unknown Customer"

    df["customer_name"] = (
        df["customer_name"]
        .fillna("Unknown Customer")
        .astype(str)
        .str.strip()
    )

    if "customer_id" not in df.columns:
        df["customer_id"] = (
            df["customer_name"]
            .str.lower()
            .str.replace(r"[^a-z0-9]+", "-", regex=True)
            .str.strip("-")
            .replace("", "unknown-customer")
            .map(lambda value: f"cust-{value}")
        )

    if "invoice_id" not in df.columns:
        df["invoice_id"] = [
            f"INV-{index + 1:04d}"
            for index in range(len(df))
        ]

    if "currency" not in df.columns:
        df["currency"] = "INR"

    if "payment_status" in df.columns:
        status = df["payment_status"].astype(str).str.strip()
        unknown_mask = status.str.lower().isin(
            {"", "unknown", "nan", "none"}
        )

        df.loc[unknown_mask & (df["paid_amount"] <= 0), "payment_status"] = "Unpaid"
        df.loc[unknown_mask & (df["paid_amount"] > 0) & (df["outstanding_amount"] > 0), "payment_status"] = "Partially Paid"
        df.loc[unknown_mask & (df["outstanding_amount"] <= 0) & (df["invoice_amount"] > 0), "payment_status"] = "Paid"

    if "communication_status" not in df.columns:
        df["communication_status"] = "Unknown"

    if "dispute_status" not in df.columns:
        df["dispute_status"] = "None"

    return df


def calculate_risk(
    row: pd.Series,
) -> tuple[int, list[str]]:

    score = 0
    reasons = []

    overdue_days = float(
        row.get("overdue_days", 0)
    )

    outstanding = float(
        row.get("outstanding_amount", 0)
    )

    payment_status = str(
        row.get("payment_status", "")
    ).lower()

    communication_status = str(
        row.get(
            "communication_status",
            "",
        )
    ).lower()

    if overdue_days >= 15:
        score += 30
        reasons.append(
            "Invoice is overdue by 15+ days"
        )

    if overdue_days >= 30:
        score += 20
        reasons.append(
            "Invoice is overdue by 30+ days"
        )

    if (
        payment_status
        in {
            "partial",
            "partially paid",
            "partially_paid",
        }
        and outstanding > 0
    ):
        score += 10
        reasons.append(
            "Invoice has an outstanding partial payment"
        )

    if "no response" in communication_status:
        score += 15
        reasons.append(
            "Customer has not responded"
        )

    if outstanding >= 500000:
        score += 15
        reasons.append(
            "Outstanding amount is ₹5 lakh or more"
        )

    score = min(score, 100)

    if score >= 70:
        risk_level = "HIGH"
    elif score >= 40:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return score, reasons


def recommended_action(
    row: pd.Series,
) -> str:

    dispute = str(
        row.get(
            "dispute_status",
            "",
        )
    ).lower().strip()

    if dispute not in {
        "",
        "none",
        "nan",
    }:
        return "Resolve dispute before escalation"

    overdue_days = float(
        row.get("overdue_days", 0)
    )

    if overdue_days <= 7:
        return "Friendly payment reminder"

    if overdue_days <= 15:
        return "Formal payment reminder"

    if overdue_days <= 30:
        return "Escalation review"

    return "Management review"


def calculate_overdue_days(
    due_date_value: str | None,
) -> int:

    if not due_date_value:
        return 0

    try:

        due = pd.to_datetime(
            due_date_value
        ).date()

        days = (
            date.today() - due
        ).days

        return max(
            days,
            0,
        )

    except Exception:
        return 0


# =========================================================
# ACTIVE COMPANY DATA
# =========================================================


def clear_active_company_data():
    """Remove the previous active company's transactional data."""

    init_db()
    db = SessionLocal()

    try:
        db.query(CollectionAction).delete(synchronize_session=False)
        db.query(PaymentPromise).delete(synchronize_session=False)
        db.query(Dispute).delete(synchronize_session=False)
        db.query(Communication).delete(synchronize_session=False)
        db.query(Payment).delete(synchronize_session=False)
        db.query(Invoice).delete(synchronize_session=False)
        db.query(Customer).delete(synchronize_session=False)
        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# =========================================================
# UPLOAD
# =========================================================

st.header("Company Data Upload")

if "uploader_version" not in st.session_state:
    st.session_state[
        "uploader_version"
    ] = 0


uploaded_file = st.file_uploader(
    "Upload company receivables data or an invoice",
    type=[
        "csv",
        "xlsx",
        "xls",
        "pdf",
    ],
    help=(
        "CSV/Excel files can contain receivables data. "
        "PDF files can be individual invoices."
    ),
    key=(
        "company_uploader_"
        f"{st.session_state['uploader_version']}"
    ),
)


if uploaded_file is not None:

    try:

        uploaded_bytes = (
            uploaded_file.getvalue()
        )

        saved_path = save_uploaded_file(
            uploaded_file.name,
            uploaded_bytes,
        )

        file_info = get_file_info(
            saved_path
        )

        # -------------------------------------------------
        # CSV / EXCEL
        # -------------------------------------------------

        if saved_path.suffix.lower() in {
            ".csv",
            ".xlsx",
            ".xls",
        }:

            uploaded_data = read_tabular_file(
                saved_path
            )

            uploaded_data = normalize_uploaded_data(
                uploaded_data
            )

            # A receivables file must contain the fields needed
            # to calculate aging and persist invoices.
            required_columns = {
                "invoice_id",
                "customer_name",
                "invoice_date",
                "due_date",
                "invoice_amount",
            }

            missing_columns = (
                required_columns
                - set(uploaded_data.columns)
            )

            if missing_columns:

                st.error(
                    "Missing required company columns: "
                    + ", ".join(sorted(missing_columns))
                    + ". Customer ID and currency are generated automatically."
                )

            elif uploaded_data.empty:

                st.error(
                    "The uploaded file contains no records."
                )

            elif (
                uploaded_data["invoice_amount"] <= 0
            ).all():

                st.error(
                    "No valid invoice amounts were found."
                )

            else:

                # Recalculate aging from the uploaded due dates
                # when the file does not provide valid overdue days.
                uploaded_data["overdue_days"] = uploaded_data.apply(
                    lambda row: (
                        int(row["overdue_days"])
                        if int(row.get("overdue_days", 0)) > 0
                        else calculate_overdue_days(
                            str(row.get("due_date", ""))
                        )
                    ),
                    axis=1,
                )

                st.subheader(
                    "New Company Data Preview"
                )

                st.dataframe(
                    uploaded_data.head(100),
                    use_container_width=True,
                    hide_index=True,
                )

                st.warning(
                    "Replacing company data will remove the previous "
                    "customers, invoices, payments, communications, disputes "
                    "and collection records from the active database."
                )

                replace_company_data = st.button(
                    "Replace Current Company Data",
                    type="primary",
                    use_container_width=True,
                    key=(
                        "replace_company_data_"
                        f"{st.session_state['uploader_version']}"
                    ),
                )

                if replace_company_data:

                    try:

                        # Remove previous active company's data first.
                        clear_active_company_data()

                        # Old payment transactions belong to the previous
                        # company dataset, so remove them as well.
                        old_payment_file = (
                            BASE_DIR
                            / "data"
                            / "runtime"
                            / "payments.csv"
                        )

                        if old_payment_file.exists():
                            old_payment_file.unlink()

                        st.session_state.pop(
                            "company_payments",
                            None,
                        )

                        st.session_state.pop(
                            "payment_file_name",
                            None,
                        )

                        st.session_state.pop(
                            "reconciled_receivables",
                            None,
                        )

                        runtime_dir = (
                            BASE_DIR
                            / "data"
                            / "runtime"
                        )

                        runtime_dir.mkdir(
                            parents=True,
                            exist_ok=True,
                        )

                        company_path = (
                            runtime_dir
                            / "company_receivables.csv"
                        )

                        uploaded_data.to_csv(
                            company_path,
                            index=False,
                        )

                        # Make the new file the active Streamlit dataset.
                        st.session_state[
                            "company_receivables"
                        ] = uploaded_data.copy()

                        st.session_state[
                            "company_file_name"
                        ] = uploaded_file.name

                        # Persist the same dataset in SQLite.
                        sync_result = sync_runtime_data()

                        st.success(
                            "New company data uploaded. "
                            "Previous active company data was replaced."
                        )

                        c1, c2, c3 = st.columns(3)

                        with c1:
                            st.metric(
                                "Invoices",
                                len(uploaded_data),
                            )

                        with c2:
                            st.metric(
                                "Customers",
                                uploaded_data[
                                    "customer_id"
                                ].nunique(),
                            )

                        with c3:
                            st.metric(
                                "Invoices in Database",
                                sync_result.get(
                                    "invoices_created",
                                    0,
                                ),
                            )

                        st.info(
                            "The new dataset is now active for the "
                            "Dashboard and database-backed AI features."
                        )

                    except Exception as error:

                        st.error(
                            "Company data replacement failed: "
                            f"{error}"
                        )

                        st.exception(error)

        # -------------------------------------------------
        # PDF
        # -------------------------------------------------

        elif saved_path.suffix.lower() == ".pdf":

            st.success(
                "PDF invoice uploaded."
            )

            try:

                extracted = extract_invoice_fields(
                    saved_path
                )

                if not extracted[
                    "text_extracted"
                ]:

                    st.warning(
                        "No text could be extracted from this PDF. "
                        "This may be a scanned/image-only invoice. "
                        "OCR will be required."
                    )

                else:

                    st.subheader(
                        "Extracted Invoice — Review Before Adding"
                    )

                    st.caption(
                        "CashFlowAI does not automatically trust "
                        "financial data extracted from a PDF. "
                        "Review and confirm the fields first."
                    )

                    pdf_col1, pdf_col2 = st.columns(2)

                    with pdf_col1:

                        invoice_number = st.text_input(
                            "Invoice Number",
                            value=(
                                extracted[
                                    "invoice_number"
                                ]
                                or ""
                            ),
                        )

                        customer_name = st.text_input(
                            "Customer Name",
                            value=(
                                extracted[
                                    "customer_name"
                                ]
                                or ""
                            ),
                        )

                        invoice_date = st.text_input(
                            "Invoice Date",
                            value=(
                                extracted[
                                    "invoice_date"
                                ]
                                or ""
                            ),
                        )

                        due_date = st.text_input(
                            "Due Date",
                            value=(
                                extracted[
                                    "due_date"
                                ]
                                or ""
                            ),
                        )

                    with pdf_col2:

                        po_number = st.text_input(
                            "PO Number",
                            value=(
                                extracted[
                                    "po_number"
                                ]
                                or ""
                            ),
                        )

                        invoice_amount = st.number_input(
                            "Invoice Amount",
                            min_value=0.0,
                            value=float(
                                extracted[
                                    "invoice_amount"
                                ]
                                or 0
                            ),
                            step=1000.0,
                        )

                        tax_amount = st.number_input(
                            "Tax Amount",
                            min_value=0.0,
                            value=float(
                                extracted[
                                    "tax_amount"
                                ]
                                or 0
                            ),
                            step=1000.0,
                        )

                        overdue_days = calculate_overdue_days(
                            due_date
                        )

                        st.metric(
                            "Calculated Overdue Days",
                            overdue_days,
                        )

                    st.divider()

                    raw_text_expander = st.expander(
                        "View extracted PDF text"
                    )

                    with raw_text_expander:
                        st.text(
                            extracted["raw_text"]
                        )

                    approve_pdf = st.button(
                        "Confirm & Add Invoice",
                        type="primary",
                    )

                    if approve_pdf:

                        if not invoice_number.strip():
                            st.error(
                                "Invoice number is required."
                            )
                            st.stop()

                        if not customer_name.strip():
                            st.error(
                                "Customer name is required."
                            )
                            st.stop()

                        if invoice_amount <= 0:
                            st.error(
                                "Invoice amount must be greater than zero."
                            )
                            st.stop()

                        new_invoice = pd.DataFrame(
                            [
                                {
                                    "invoice_id": invoice_number.strip(),
                                    "customer_name": customer_name.strip(),
                                    "invoice_date": invoice_date.strip(),
                                    "due_date": due_date.strip(),
                                    "po_number": po_number.strip(),
                                    "invoice_amount": invoice_amount,
                                    "tax_amount": tax_amount,
                                    "paid_amount": 0,
                                    "outstanding_amount": invoice_amount,
                                    "payment_status": "Unpaid",
                                    "overdue_days": overdue_days,
                                    "last_payment_date": "",
                                    "last_communication_date": "",
                                    "communication_status": "No Communication",
                                    "dispute_status": "None",
                                    "source": "PDF",
                                    "source_file": uploaded_file.name,
                                }
                            ]
                        )

                        new_invoice = (
                            normalize_uploaded_data(
                                new_invoice
                            )
                        )

                        if (
                            "company_receivables"
                            in st.session_state
                        ):

                            current_data = (
                                st.session_state[
                                    "company_receivables"
                                ]
                            )

                            combined = pd.concat(
                                [
                                    current_data,
                                    new_invoice,
                                ],
                                ignore_index=True,
                            )

                        else:

                            combined = new_invoice

                        st.session_state[
                            "company_receivables"
                        ] = combined

                        st.session_state[
                            "company_file_name"
                        ] = (
                            "Company data + "
                            f"{uploaded_file.name}"
                        )

                        st.success(
                            "Invoice confirmed and added to CashFlowAI."
                        )

                        st.rerun()

            except Exception as error:

                st.error(
                    "PDF invoice extraction failed: "
                    f"{error}"
                )

    except Exception as error:

        st.error(
            f"Unable to process uploaded file: {error}"
        )


# =========================================================
# PAYMENT DATA
# =========================================================

st.divider()

st.header("Payment Data")

if "payment_uploader_version" not in st.session_state:
    st.session_state["payment_uploader_version"] = 0

payment_file = st.file_uploader(
    "Upload payment CSV",
    type=["csv"],
    help="Upload payment transactions containing invoice_id, payment_date and payment_amount.",
    key=f"payment_uploader_{st.session_state['payment_uploader_version']}",
)

if payment_file is not None:

    try:

        payment_path = save_uploaded_file(
            payment_file.name,
            payment_file.getvalue(),
        )

        payment_data = read_tabular_file(
            payment_path
        )

        payment_data.columns = [
            str(column).strip().lower()
            for column in payment_data.columns
        ]

        required_columns = {
            "invoice_id",
            "payment_date",
            "payment_amount",
        }

        missing_columns = (
            required_columns
            - set(payment_data.columns)
        )

        if missing_columns:

            st.error(
                "Missing payment columns: "
                + ", ".join(
                    sorted(missing_columns)
                )
            )

        else:

            st.session_state[
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

            st.success(
                "Payment CSV uploaded successfully."
            )

            st.dataframe(
                payment_data,
                use_container_width=True,
                hide_index=True,
            )

    except Exception as error:

        st.error(
            f"Unable to load payment CSV: {error}"
        )

# =========================================================
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


if receivables.empty:

    st.warning(
        "No receivables data available."
    )

    st.stop()


# =========================================================
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

if (
    "company_payments"
    in st.session_state
):

    payment_data = (
        st.session_state[
            "company_payments"
        ].copy()
    )

    try:

        reconciliation = (
            build_reconciliation_report(
                receivables,
                payment_data,
            )
        )

        reconciled_data = (
            reconciliation[
                "reconciled"
            ].copy()
        )

        unmatched_payments = (
            reconciliation[
                "unmatched_payments"
            ].copy()
        )

        duplicate_payments = (
            reconciliation[
                "duplicate_payments"
            ].copy()
        )

        receivables = reconciled_data

        st.session_state[
            "reconciled_receivables"
        ] = reconciled_data

        st.subheader(
            "Payment Reconciliation"
        )

        rc1, rc2, rc3, rc4 = st.columns(4)

        with rc1:
            paid_total = pd.to_numeric(
                reconciled_data[
                    "paid_amount"
                ],
                errors="coerce",
            ).fillna(0).sum()

            st.metric(
                "Total Paid",
                f"₹{paid_total:,.0f}",
            )

        with rc2:
            outstanding_total = pd.to_numeric(
                reconciled_data[
                    "outstanding_amount"
                ],
                errors="coerce",
            ).fillna(0).sum()

            st.metric(
                "Outstanding",
                f"₹{outstanding_total:,.0f}",
            )

        with rc3:
            st.metric(
                "Unmatched Payments",
                len(unmatched_payments),
            )

        with rc4:
            st.metric(
                "Duplicate Payments",
                len(duplicate_payments),
            )

        with st.expander(
            "View reconciled invoices"
        ):

            st.dataframe(
                reconciled_data[
                    [
                        "invoice_id",
                        "invoice_amount",
                        "paid_amount",
                        "outstanding_amount",
                        "payment_status",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

        if not unmatched_payments.empty:

            st.warning(
                "Unmatched payments detected."
            )

            st.dataframe(
                unmatched_payments[
                    [
                        "invoice_id",
                        "customer_name",
                        "payment_date",
                        "payment_amount",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

        if not duplicate_payments.empty:

            st.warning(
                "Duplicate payments detected. "
                "Duplicates are excluded from the paid total."
            )

            st.dataframe(
                duplicate_payments[
                    [
                        "invoice_id",
                        "customer_name",
                        "payment_date",
                        "payment_amount",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

    except Exception as error:

        st.error(
            "Payment reconciliation failed: "
            f"{error}"
        )


# =========================================================
# DASHBOARD METRICS
# =========================================================

total_outstanding = (
    receivables[
        "outstanding_amount"
    ].sum()
)

overdue_mask = (
    (
        receivables[
            "overdue_days"
        ] > 0
    )
    & (
        receivables[
            "outstanding_amount"
        ] > 0
    )
)

total_overdue = (
    receivables.loc[
        overdue_mask,
        "outstanding_amount",
    ].sum()
)

overdue_15 = (
    receivables.loc[
        receivables[
            "overdue_days"
        ] >= 15,
        "outstanding_amount",
    ].sum()
)

overdue_30 = (
    receivables.loc[
        receivables[
            "overdue_days"
        ] >= 30,
        "outstanding_amount",
    ].sum()
)

status_series = (
    receivables[
        "payment_status"
    ]
    .astype(str)
    .str.lower()
    .str.strip()
)

unpaid_count = int(
    status_series.isin(
        [
            "unpaid",
            "pending",
        ]
    ).sum()
)

partial_count = int(
    status_series.isin(
        [
            "partial",
            "partially paid",
            "partially_paid",
        ]
    ).sum()
)

overdue_count = int(
    overdue_mask.sum()
)


# =========================================================
# DASHBOARD
# =========================================================

st.header("Dashboard")

col1, col2, col3, col4 = (
    st.columns(4)
)

with col1:
    st.metric(
        "Total Outstanding",
        f"₹{total_outstanding:,.0f}",
    )

with col2:
    st.metric(
        "Total Overdue",
        f"₹{total_overdue:,.0f}",
    )

with col3:
    st.metric(
        "Overdue ≥15 Days",
        f"₹{overdue_15:,.0f}",
    )

with col4:
    st.metric(
        "Overdue ≥30 Days",
        f"₹{overdue_30:,.0f}",
    )


col1, col2, col3, col4 = (
    st.columns(4)
)

with col1:
    st.metric(
        "Total Invoices",
        len(receivables),
    )

with col2:
    st.metric(
        "Unpaid Invoices",
        unpaid_count,
    )

with col3:
    st.metric(
        "Partially Paid",
        partial_count,
    )

with col4:
    st.metric(
        "Overdue Invoices",
        overdue_count,
    )


# =========================================================
# AI COLLECTION RISK
# =========================================================

st.divider()

st.header(
    "AI Collection Risk"
)

risk_rows = []

for _, row in receivables.iterrows():

    score, reasons = calculate_risk(
        row
    )

    if score >= 70:
        level = "HIGH"
    elif score >= 40:
        level = "MEDIUM"
    else:
        level = "LOW"

    risk_rows.append(
        {
            "customer_name": row.get(
                "customer_name",
                "Unknown",
            ),
            "invoice_id": row.get(
                "invoice_id",
                "Unknown",
            ),
            "outstanding_amount": row.get(
                "outstanding_amount",
                0,
            ),
            "overdue_days": row.get(
                "overdue_days",
                0,
            ),
            "risk_score": score,
            "risk_level": level,
            "risk_reasons": (
                "; ".join(reasons)
                if reasons
                else "No major risk signals"
            ),
            "recommended_action": (
                recommended_action(row)
            ),
        }
    )


risk_df = pd.DataFrame(
    risk_rows
)

high_count = int(
    (
        risk_df[
            "risk_level"
        ]
        == "HIGH"
    ).sum()
)

medium_count = int(
    (
        risk_df[
            "risk_level"
        ]
        == "MEDIUM"
    ).sum()
)

low_count = int(
    (
        risk_df[
            "risk_level"
        ]
        == "LOW"
    ).sum()
)


r1, r2, r3 = st.columns(3)

with r1:
    st.metric(
        "High Risk",
        high_count,
    )

with r2:
    st.metric(
        "Medium Risk",
        medium_count,
    )

with r3:
    st.metric(
        "Low Risk",
        low_count,
    )


risk_filter = st.selectbox(
    "Risk Level Filter",
    [
        "All",
        "HIGH",
        "MEDIUM",
        "LOW",
    ],
)

display_risk = risk_df.copy()

if risk_filter != "All":

    display_risk = (
        display_risk[
            display_risk[
                "risk_level"
            ]
            == risk_filter
        ]
    )


st.dataframe(
    display_risk,
    use_container_width=True,
    hide_index=True,
)


# =========================================================
# RECEIVABLES
# =========================================================

st.divider()

st.header(
    "Receivables"
)

filter_col1, filter_col2 = (
    st.columns(2)
)

with filter_col1:

    overdue_filter = st.selectbox(
        "Overdue Filter",
        [
            "All",
            "Overdue",
            "15+ Days",
            "30+ Days",
        ],
    )

with filter_col2:

    search_text = st.text_input(
        "Search Customer or Invoice",
        placeholder=(
            "Customer name or invoice ID"
        ),
    )


filtered_receivables = (
    receivables.copy()
)


if overdue_filter == "Overdue":

    filtered_receivables = (
        filtered_receivables[
            filtered_receivables[
                "overdue_days"
            ] > 0
        ]
    )

elif overdue_filter == "15+ Days":

    filtered_receivables = (
        filtered_receivables[
            filtered_receivables[
                "overdue_days"
            ] >= 15
        ]
    )

elif overdue_filter == "30+ Days":

    filtered_receivables = (
        filtered_receivables[
            filtered_receivables[
                "overdue_days"
            ] >= 30
        ]
    )


if search_text.strip():

    search_value = (
        search_text.strip().lower()
    )

    search_mask = pd.Series(
        False,
        index=filtered_receivables.index,
    )

    for column_name in [
        "customer_name",
        "invoice_id",
    ]:

        if column_name in (
            filtered_receivables.columns
        ):

            search_mask = (
                search_mask
                | filtered_receivables[
                    column_name
                ]
                .astype(str)
                .str.lower()
                .str.contains(
                    search_value,
                    na=False,
                )
            )

    filtered_receivables = (
        filtered_receivables[
            search_mask
        ]
    )


st.caption(
    f"Showing "
    f"{len(filtered_receivables):,} "
    "receivables"
)

st.dataframe(
    filtered_receivables,
    use_container_width=True,
    hide_index=True,
)


# =========================================================
# CLEAR COMPANY DATA
# =========================================================

st.divider()

if (
    "company_receivables"
    in st.session_state
):

    if st.button(
        "Clear Uploaded Company Data"
    ):

        st.session_state.pop(
            "company_receivables",
            None,
        )

        st.session_state.pop(
            "company_file_name",
            None,
        )

        st.session_state[
            "uploader_version"
        ] += 1

        st.rerun()


st.caption(
    "Financial calculations are deterministic. "
    "Extracted PDF data requires human confirmation. "
    "Human approval is required before real customer communication."
)






