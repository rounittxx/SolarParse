# Best-effort text extraction. We try the cheap path first (digital PDF
# text layer via pdfplumber) and only fall back to OCR if that comes back
# basically empty -- which is what scanned MSEDCL bills look like.

import io
from pathlib import Path

import pdfplumber
from pdf2image import convert_from_bytes


MIN_USEFUL_CHARS = 80   # arbitrary; if a page has less than this, it's almost certainly scanned


def extract_text_from_pdf(pdf_bytes: bytes) -> tuple[str, list]:
    """
    Returns (combined_text, page_images).
    page_images is a list of PIL.Image -- we always render them too,
    because the LLM works much better when given the actual image of
    the bill, even if we already have the text layer.
    """
    text_chunks = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            text_chunks.append(t.strip())

    combined = "\n\n".join(c for c in text_chunks if c).strip()

    # Always render images too. They're cheap to produce and the vision
    # model uses them as the source of truth for layout-heavy bills.
    try:
        images = convert_from_bytes(pdf_bytes, dpi=200)
    except Exception:
        # poppler not installed? fine, return empty list and let the
        # OCR/LLM path use whatever text we have.
        images = []

    return combined, images


def looks_like_scanned(text: str) -> bool:
    return len(text.strip()) < MIN_USEFUL_CHARS


def load_pdf_bytes(path: str | Path) -> bytes:
    return Path(path).read_bytes()
