from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from app.services.pdf_processor import extract_pdf_text


DATE_PATTERNS = [
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
]


def clean_value(value: str | None) -> str | None:
    if not value:
        return None

    value = value.strip()

    if not value:
        return None

    return value


def find_first(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            return clean_value(
                match.group(1)
            )

    return None


def parse_amount(value: str | None) -> float | None:
    if not value:
        return None

    cleaned = (
        value.replace(",", "")
        .replace("₹", "")
        .replace("Rs.", "")
        .replace("Rs", "")
        .strip()
    )

    match = re.search(
        r"\d+(?:\.\d+)?",
        cleaned,
    )

    if not match:
        return None

    try:
        return float(match.group())
    except ValueError:
        return None


def parse_date(value: str | None) -> str | None:
    if not value:
        return None

    for date_pattern in DATE_PATTERNS:

        match = re.search(
            date_pattern,
            value,
        )

        if not match:
            continue

        raw_date = match.group()

        for fmt in (
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d/%m/%y",
            "%d-%m-%y",
            "%Y/%m/%d",
            "%Y-%m-%d",
        ):

            try:

                parsed = datetime.strptime(
                    raw_date,
                    fmt,
                )

                return parsed.strftime(
                    "%Y-%m-%d"
                )

            except ValueError:
                continue

    return None


def extract_invoice_fields(
    pdf_path: Path,
) -> dict:

    result = extract_pdf_text(
        pdf_path
    )

    text = result["text"]

    invoice_number = find_first(
        [
            r"invoice\s*(?:no|number|#)\s*[:\-]?\s*([A-Za-z0-9\/\-_]+)",
            r"bill\s*(?:no|number|#)\s*[:\-]?\s*([A-Za-z0-9\/\-_]+)",
        ],
        text,
    )

    customer_name = find_first(
        [
            r"(?:customer|bill\s*to|buyer|client)\s*[:\-]\s*(.+)",
        ],
        text,
    )

    invoice_date_raw = find_first(
        [
            r"invoice\s*date\s*[:\-]?\s*([0-9\/\-]+)",
            r"date\s*[:\-]?\s*([0-9\/\-]+)",
        ],
        text,
    )

    due_date_raw = find_first(
        [
            r"due\s*date\s*[:\-]?\s*([0-9\/\-]+)",
            r"payment\s*due\s*[:\-]?\s*([0-9\/\-]+)",
        ],
        text,
    )

    po_number = find_first(
        [
            r"(?:po|p\.o\.|purchase\s*order)\s*(?:no|number|#)?\s*[:\-]?\s*([A-Za-z0-9\/\-_]+)",
        ],
        text,
    )

    total_amount_raw = find_first(
        [
            r"(?:grand\s*total|total\s*amount|invoice\s*total|net\s*payable|amount\s*due)\s*[:\-]?\s*[₹rs\.]*\s*([\d,]+(?:\.\d{1,2})?)",
        ],
        text,
    )

    tax_amount_raw = find_first(
        [
            r"(?:gst|tax|igst|cgst|sgst)\s*(?:amount)?\s*[:\-]?\s*[₹rs\.]*\s*([\d,]+(?:\.\d{1,2})?)",
        ],
        text,
    )

    invoice_date = parse_date(
        invoice_date_raw
    )

    due_date = parse_date(
        due_date_raw
    )

    invoice_amount = parse_amount(
        total_amount_raw
    )

    tax_amount = parse_amount(
        tax_amount_raw
    )

    return {
        "invoice_number": invoice_number,
        "customer_name": customer_name,
        "invoice_date": invoice_date,
        "due_date": due_date,
        "po_number": po_number,
        "invoice_amount": invoice_amount,
        "tax_amount": tax_amount,
        "page_count": result["page_count"],
        "text_extracted": result["has_text"],
        "raw_text": text,
    }


if __name__ == "__main__":

    print("=" * 60)
    print("     CASHFLOWAI INVOICE PDF EXTRACTOR")
    print("=" * 60)
    print()
    print(
        "Invoice extraction service is ready."
    )
    print()
    print("Fields supported:")
    print("- Invoice number")
    print("- Customer name")
    print("- Invoice date")
    print("- Due date")
    print("- PO number")
    print("- Invoice amount")
    print("- Tax amount")
    print()
    print(
        "✓ Invoice PDF extractor ready."
    )
