"""
utils/pdf_parser.py
Extract raw text from PDF files using PyMuPDF.

Only text a human reader can see is returned. Spans used to hide prompt-injection or
keyword-stuffing payloads are dropped: white / near-white text that is not drawn over a
dark shape or image, text smaller than MIN_FONT_SIZE_PT, fully transparent text and text
placed outside the page. Work per file is bounded by MAX_PAGES and MAX_CHARS.
Password-protected PDFs raise PDFPasswordError (a ValueError) with a user-presentable message.
"""

import logging
import re

try:
    import pymupdf
except ImportError:  # older PyMuPDF releases only ship the legacy module name
    import fitz as pymupdf

logger = logging.getLogger(__name__)

MAX_PAGES = 30
MAX_CHARS = 60_000
MIN_FONT_SIZE_PT = 3.0
_LIGHT_CHANNEL_MIN = 0xF0      # every RGB channel ≥ this → "white" text
_DARK_LUMINANCE_MAX = 0.6      # filled shapes darker than this make light text visible


class PDFPasswordError(ValueError):
    """Raised when a PDF is encrypted and cannot be opened without a password."""


def _is_light_text(srgb: int) -> bool:
    r, g, b = (srgb >> 16) & 0xFF, (srgb >> 8) & 0xFF, srgb & 0xFF
    return min(r, g, b) >= _LIGHT_CHANNEL_MIN


def _dark_backgrounds(page) -> list:
    """Rects of dark filled shapes and images — light text drawn on top of them is visible."""
    rects = []
    try:
        for drawing in page.get_drawings():
            fill = drawing.get("fill")
            if not fill or len(fill) < 3:
                continue
            luminance = 0.2126 * fill[0] + 0.7152 * fill[1] + 0.0722 * fill[2]
            if luminance < _DARK_LUMINANCE_MAX:
                rects.append(pymupdf.Rect(drawing["rect"]))
        for info in page.get_image_info():
            rects.append(pymupdf.Rect(info["bbox"]))
    except Exception as exc:
        logger.debug("Could not inspect PDF page backgrounds (%s)", type(exc).__name__)
    return rects


def _page_visible_text(page) -> tuple[str, int]:
    """Visible text of one page and the number of hidden spans dropped."""
    page_rect = page.rect
    backgrounds = None
    dropped = 0
    block_texts = []
    data = page.get_text("dict")
    for block in data.get("blocks", []):
        if block.get("type", 0) != 0:
            continue
        line_texts = []
        for line in block.get("lines", []):
            kept = []
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text.strip():
                    kept.append(text)
                    continue
                bbox = pymupdf.Rect(span.get("bbox", (0, 0, 0, 0)))
                hidden = (
                    span.get("size", 12) < MIN_FONT_SIZE_PT
                    or span.get("alpha", 255) == 0
                    or not bbox.intersects(page_rect)
                )
                if not hidden and _is_light_text(int(span.get("color", 0))):
                    if backgrounds is None:
                        backgrounds = _dark_backgrounds(page)
                    centre = pymupdf.Point((bbox.x0 + bbox.x1) / 2, (bbox.y0 + bbox.y1) / 2)
                    hidden = not any(centre in rect for rect in backgrounds)
                if hidden:
                    dropped += 1
                    continue
                kept.append(text)
            line_text = "".join(kept)
            if line_text.strip():
                line_texts.append(line_text)
        if line_texts:
            block_texts.append("\n".join(line_texts))
    return "\n".join(block_texts), dropped


def extract_pdf_text_with_flags(file_path: str) -> tuple[str, dict]:
    """
    Extract visible text from a PDF file.

    Returns:
        (text, flags) where flags = {
            "hidden_spans_dropped": int,  # white / tiny / transparent / off-page spans removed
            "pages_total": int,
            "pages_truncated": bool,      # more than MAX_PAGES pages
            "chars_truncated": bool,      # more than MAX_CHARS characters
        }

    Raises:
        PDFPasswordError (ValueError): the PDF is password-protected.
    """
    flags = {"hidden_spans_dropped": 0, "pages_total": 0, "pages_truncated": False, "chars_truncated": False}
    text_parts = []
    doc = None

    try:
        doc = pymupdf.open(file_path)
        if doc.needs_pass and not doc.authenticate(""):
            raise PDFPasswordError("PDF is password-protected")

        flags["pages_total"] = doc.page_count
        flags["pages_truncated"] = doc.page_count > MAX_PAGES
        total_chars = 0
        for page_num in range(min(doc.page_count, MAX_PAGES)):
            page = doc.load_page(page_num)
            page_text, dropped = _page_visible_text(page)
            flags["hidden_spans_dropped"] += dropped
            if page_text.strip():
                text_parts.append(page_text)
                total_chars += len(page_text)
            if total_chars >= MAX_CHARS:
                flags["chars_truncated"] = True
                break
    except PDFPasswordError:
        raise
    except Exception as exc:
        # Never log file names or content — only the error type
        logger.warning("PDF text extraction failed (%s)", type(exc).__name__)
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass

    full_text = "\n".join(text_parts)

    # Light clean-up: collapse 3+ blank lines into 2
    full_text = re.sub(r"\n{3,}", "\n\n", full_text).strip()
    if len(full_text) > MAX_CHARS:
        full_text = full_text[:MAX_CHARS]
        flags["chars_truncated"] = True

    if flags["hidden_spans_dropped"]:
        logger.warning("Dropped %d hidden or tiny text spans from a PDF", flags["hidden_spans_dropped"])
    if flags["pages_truncated"]:
        logger.info("PDF has %d pages; only the first %d were read", flags["pages_total"], MAX_PAGES)

    return full_text, flags


def extract_pdf_text(file_path: str) -> str:
    """
    Extract all visible text from a PDF file.

    Args:
        file_path: Absolute or relative path to the .pdf file.

    Returns:
        A single string with all extracted text (newlines preserved).
        Returns an empty string if extraction fails.

    Raises:
        PDFPasswordError (ValueError): the PDF is password-protected.
    """
    text, _ = extract_pdf_text_with_flags(file_path)
    return text
