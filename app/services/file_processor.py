from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pandas as pd


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

UPLOAD_DIR = BASE_DIR / "data" / "uploads"

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".csv",
    ".xlsx",
    ".xls",
}


# ============================================================
# VALIDATION
# ============================================================

def validate_file(file_path: Path) -> None:
    """
    Validate that the uploaded file type is supported.
    """

    extension = file_path.suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {extension}. "
            "Supported files are PDF, CSV, XLSX and XLS."
        )


# ============================================================
# SAVE UPLOAD
# ============================================================

def save_uploaded_file(
    file_name: str,
    file_bytes: bytes,
) -> Path:
    """
    Save an uploaded company file to the local
    CashFlowAI upload directory.

    A unique ID is added to avoid filename collisions.
    """

    original_name = Path(file_name).name

    extension = Path(original_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. "
            "Please upload PDF, CSV or Excel files."
        )

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    unique_name = (
        f"{uuid4().hex[:8]}_{original_name}"
    )

    destination = UPLOAD_DIR / unique_name

    with open(
        destination,
        "wb",
    ) as file:

        file.write(file_bytes)

    return destination


# ============================================================
# CSV READER
# ============================================================

def read_csv_file(
    file_path: Path,
) -> pd.DataFrame:
    """
    Read a CSV file into a DataFrame.
    """

    validate_file(file_path)

    return pd.read_csv(
        file_path
    )


# ============================================================
# EXCEL READER
# ============================================================

def read_excel_file(
    file_path: Path,
) -> pd.DataFrame:
    """
    Read the first sheet of an Excel file.
    """

    validate_file(file_path)

    return pd.read_excel(
        file_path
    )


# ============================================================
# GENERIC TABULAR READER
# ============================================================

def read_tabular_file(
    file_path: Path,
) -> pd.DataFrame:
    """
    Read CSV or Excel files.
    """

    extension = file_path.suffix.lower()

    if extension == ".csv":

        return read_csv_file(
            file_path
        )

    if extension in {
        ".xlsx",
        ".xls",
    }:

        return read_excel_file(
            file_path
        )

    raise ValueError(
        "The uploaded file is not a CSV "
        "or Excel file."
    )


# ============================================================
# FILE INFORMATION
# ============================================================

def get_file_info(
    file_path: Path,
) -> dict:
    """
    Return basic information about
    an uploaded file.
    """

    if not file_path.exists():

        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    return {
        "file_name": file_path.name,
        "file_type": file_path.suffix.lower(),
        "file_size_bytes": file_path.stat().st_size,
        "file_path": str(file_path),
    }


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("       CASHFLOWAI FILE PROCESSOR")
    print("=" * 60)

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "\nUpload directory:"
    )

    print(
        UPLOAD_DIR
    )

    print(
        "\nSupported file types:"
    )

    for extension in sorted(
        ALLOWED_EXTENSIONS
    ):

        print(
            f"- {extension}"
        )

    print(
        "\n✓ File processor is ready."
    )