"""
PDF text extraction with dual-library fallback: PyMuPDF (primary) → pdfminer.six (fallback).
"""

import logging

log = logging.getLogger(__name__)

PAGE_SEPARATOR = "\n\n--- PAGE BREAK ---\n\n"
MIN_TEXT_LENGTH = 50


def _extract_pymupdf(pdf_path: str) -> str:
    """Extract text using PyMuPDF (fitz). Returns concatenated page text."""
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf  # older import name

    doc = pymupdf.open(pdf_path)
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return PAGE_SEPARATOR.join(pages)


def _extract_pymupdf_markdown(pdf_path: str) -> str:
    """Extract text as markdown using pymupdf4llm (for Claude fallback path)."""
    try:
        import pymupdf4llm
        return pymupdf4llm.to_markdown(pdf_path)
    except ImportError:
        # Fall back to plain text if pymupdf4llm not installed
        return _extract_pymupdf(pdf_path)


def _extract_pdfminer(pdf_path: str) -> str:
    """Extract text using pdfminer.six. Returns full document text."""
    from pdfminer.high_level import extract_text
    return extract_text(pdf_path)


def extract_pdf_text(pdf_path: str, mode: str = "plain") -> str:
    """
    Extract full text from a PDF file.

    Args:
        pdf_path: Absolute or relative path to the PDF file.
        mode: "plain" (default) for rule-based parsers, "markdown" for Claude fallback.

    Returns:
        Extracted text string.
        Prefixed with "[ERROR:..." on total failure.
        Prefixed with "[WARNING:LOW_TEXT]" if text appears garbled/scanned (< 50 chars).
    """
    text = ""

    # Primary: PyMuPDF
    try:
        if mode == "markdown":
            text = _extract_pymupdf_markdown(pdf_path)
        else:
            text = _extract_pymupdf(pdf_path)
    except Exception as e:
        log.warning("PyMuPDF extraction failed: %s", e)

    # Fallback: pdfminer.six if PyMuPDF produced poor results
    if len(text.strip()) < MIN_TEXT_LENGTH:
        try:
            pdfminer_text = _extract_pdfminer(pdf_path)
            if len(pdfminer_text.strip()) > len(text.strip()):
                log.info("Using pdfminer.six fallback (better result)")
                text = pdfminer_text
        except Exception as e:
            log.warning("pdfminer.six fallback also failed: %s", e)

    # Total failure
    if not text.strip():
        return f"[ERROR:NO_TEXT] Could not extract any text from {pdf_path}"

    # Quality gate
    if len(text.strip()) < MIN_TEXT_LENGTH:
        return f"[WARNING:LOW_TEXT] {text}"

    return text
