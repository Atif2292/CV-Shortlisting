"""
utils/pdf_parser.py
Extract raw text from PDF files using PyMuPDF (fitz).
Falls back to basic extraction if the PDF is image-only / scanned.
"""

import re
import fitz  # PyMuPDF


def extract_pdf_text(file_path: str) -> str:
    """
    Extract all text from a PDF file.

    Args:
        file_path: Absolute or relative path to the .pdf file.

    Returns:
        A single string with all extracted text (newlines preserved).
        Returns an empty string if extraction fails.
    """
    text_parts = []

    try:
        doc = fitz.open(file_path)

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # get_text("text") returns plain-text; "blocks" gives layout-aware blocks
            page_text = page.get_text("text")
            if page_text.strip():
                text_parts.append(page_text)

        doc.close()
    except fitz.FileDataError as exc:
        print(f"[pdf_parser] File data error for {file_path}: {exc}")
    except Exception as exc:
        print(f"[pdf_parser] Unexpected error for {file_path}: {exc}")

    full_text = "\n".join(text_parts)

    # Light clean-up: collapse 3+ blank lines into 2
    full_text = re.sub(r"\n{3,}", "\n\n", full_text)

    return full_text.strip()
