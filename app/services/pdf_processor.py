from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BASE_DIR / "data" / "uploads"


def extract_pdf_text(file_path: Path) -> dict:
    """Extract text from every page of a PDF."""

    if not file_path.exists():
        raise FileNotFoundError(
            f"PDF file not found: {file_path}"
        )

    if file_path.suffix.lower() != ".pdf":
        raise ValueError(
            "The supplied file is not a PDF."
        )

    reader = PdfReader(str(file_path))

    pages = []
    full_text_parts = []

    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):
        text = page.extract_text() or ""

        pages.append(
            {
                "page_number": page_number,
                "text": text,
            }
        )

        if text.strip():
            full_text_parts.append(text.strip())

    full_text = "\n\n".join(
        full_text_parts
    )

    return {
        "file_name": file_path.name,
        "page_count": len(reader.pages),
        "text": full_text,
        "pages": pages,
        "has_text": bool(full_text.strip()),
    }


def get_pdf_info(file_path: Path) -> dict:
    result = extract_pdf_text(file_path)

    return {
        "file_name": result["file_name"],
        "page_count": result["page_count"],
        "character_count": len(result["text"]),
        "has_text": result["has_text"],
    }


if __name__ == "__main__":
    print("=" * 60)
    print("       CASHFLOWAI PDF PROCESSOR")
    print("=" * 60)
    print()
    print("PDF extraction service is ready.")
    print()
    print("Supported:")
    print("- Text-based PDF invoices")
    print("- Multi-page PDF documents")
    print("- Page-by-page text extraction")
    print()
    print("Note:")
    print("Scanned/image-only PDFs will need OCR processing.")
    print()
    print("✓ PDF processor ready.")
