"""
Stage: DOCUMENT -> TEXT

Extracts text from an uploaded file and keeps page numbers where available
(PDF) for provenance ("Source: X, Page: 3") later in the pipeline.

For PDFs, pages with a usable text layer are read directly (fast and exact).
Pages that are empty or image-heavy (e.g. scanned) are rendered to an image
with PyMuPDF and OCR'd with Tesseract. Every PageText records whether it
came from OCR so the UI can show exactly what was extracted and where.
"""
import os
from dataclasses import dataclass
from typing import List

from app import config


class ExtractionError(Exception):
    """Raised when a document cannot be parsed. Caller should surface
    this clearly rather than swallowing it, per the 'errors should
    identify the failing stage' requirement."""
    pass


@dataclass
class PageText:
    page_number: int  # 1-indexed; 0 if the format has no page concept
    text: str
    ocr: bool = False  # True when this page's text came from Tesseract OCR


# Pages with images but only this many characters of real text (or fewer)
# get OCR'd too — they're almost always scanned/image pages with a garbage
# text layer.
_MIN_PLAIN_TEXT_ON_IMAGE_PAGE = 40


def extract_text(file_path: str, filename: str) -> List[PageText]:
    """
    Returns a list of PageText, one per page for PDFs, or a single
    PageText (page_number=0) for plain text files.
    """
    lower = filename.lower()

    if lower.endswith(".pdf"):
        return _extract_pdf(file_path)
    elif lower.endswith(".txt") or lower.endswith(".md"):
        return _extract_plain_text(file_path)
    else:
        raise ExtractionError(
            f"Unsupported file type for '{filename}'. Supported: .pdf, .txt, .md"
        )


def _extract_pdf(file_path: str) -> List[PageText]:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise ExtractionError(
            "pypdf is not installed. Run: pip install pypdf"
        ) from e

    try:
        reader = PdfReader(file_path)
    except Exception as e:
        raise ExtractionError(f"Could not open PDF: {e}") from e

    if len(reader.pages) == 0:
        raise ExtractionError("PDF has no pages.")

    # PyMuPDF is only needed to render pages for OCR (no poppler/ghostscript).
    renderer = _get_renderer(file_path)

    # Pass 1: pull the embedded text layer from every page.
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception as e:
            raise ExtractionError(f"Failed to extract text from page {i}: {e}") from e
        pages.append(PageText(page_number=i, text=text))

    # If ANY page has a real text layer, an OCR failure on another page is
    # non-fatal (leave it empty rather than reject the whole document).
    # Only a fully scanned/image-only PDF requires OCR up front.
    has_any_text = any(p.text for p in pages)
    ocr_blocked_message = None

    # Pass 2: OCR pages that are empty or image-heavy with no real text.
    for i, page in enumerate(pages, start=1):
        if page.text and not _page_needs_ocr(renderer, i, page.text):
            continue
        try:
            ocr_text = _ocr_page(renderer, i)
        except ExtractionError as e:
            if not has_any_text:
                raise
            ocr_blocked_message = str(e)
            ocr_text = ""
        if ocr_text:
            page.text, page.ocr = ocr_text, True

    if not any(p.text for p in pages):
        raise ExtractionError(
            f"No text could be extracted from this PDF. "
            + (ocr_blocked_message or "It may be a scanned/image-only PDF.")
        )

    return pages


def _page_needs_ocr(renderer, page_number: int, text: str) -> bool:
    """OCR triggers when the text layer is empty OR the page is image-heavy
    with almost no real text. Text pages (normal scan) are left untouched."""
    if not text:
        return True
    if renderer is None:
        return False
    try:
        pixmapless = renderer[page_number - 1]
        has_images = len(pixmapless.get_images()) > 0
    except Exception:
        return False
    return has_images and len(text) < _MIN_PLAIN_TEXT_ON_IMAGE_PAGE


def _get_renderer(file_path: str):
    """Returns a PyMuPDF document for image rendering, or None if PyMuPDF
    is not installed (OCR then fails with a clear installation message)."""
    try:
        # PyMuPDF >= 1.24.0 publishes the module as "pymupdf"; "fitz" still
        # works but prints a deprecation warning, so prefer the new name.
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError:
            return None
    try:
        return fitz.open(file_path)
    except Exception:
        return None


def _ocr_page(renderer, page_number: int) -> str:
    """Renders one page to an image and runs Tesseract over it."""
    if renderer is None:
        raise ExtractionError(
            "Page has no text layer (scanned/image-only PDF) but OCR support is "
            "unavailable. Install with: pip install pymupdf pytesseract pillow"
        )

    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        raise ExtractionError(
            "OCR libraries not installed. Run: pip install pymupdf pytesseract pillow"
        ) from e

    _configure_tesseract(pytesseract)
    try:
        pytesseract.get_tesseract_version()
    except Exception as e:
        raise ExtractionError(
            "Tesseract binary not found. Install Tesseract OCR (or set TESSERACT_CMD "
            "in backend/app/config.py)."
        ) from e

    try:
        page = renderer[page_number - 1]
        pix = page.get_pixmap(dpi=200)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return pytesseract.image_to_string(img).strip()
    except ExtractionError:
        raise
    except Exception as e:
        raise ExtractionError(f"OCR failed on page {page_number}: {e}") from e


def _configure_tesseract(pytesseract):
    if config.TESSERACT_CMD:
        # Accept a directory too ("C:/Apps/Tesseract") and resolve the exe,
        # even though the config default already points at the full path.
        cmd = config.TESSERACT_CMD
        if os.path.isdir(cmd):
            cmd = os.path.join(cmd, "tesseract.exe")
        pytesseract.pytesseract.tesseract_cmd = cmd
        return
    # Not on PATH? Check common Windows install locations.
    for candidate in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            return


def _extract_plain_text(file_path: str) -> List[PageText]:
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read().strip()
    except Exception as e:
        raise ExtractionError(f"Could not read text file: {e}") from e

    if not text:
        raise ExtractionError("File is empty.")

    return [PageText(page_number=0, text=text)]