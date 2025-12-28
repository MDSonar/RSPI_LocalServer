"""
Base PDF Parser with text & OCR fallback
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple

import fitz  # PyMuPDF for text extraction
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

logger = logging.getLogger(__name__)


class BaseBankParser(ABC):
    """Abstract base for bank-specific parsers."""

    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        self.doc = None
        self.logs: List[Dict] = []

    def compute_statement_hash(self) -> str:
        """Compute SHA256 hash of PDF for idempotency."""
        sha256 = hashlib.sha256()
        with open(self.pdf_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def extract_text(self, use_ocr: bool = False) -> List[str]:
        """Extract text from PDF; optional OCR fallback for scanned pages."""
        pages = []
        try:
            self.doc = fitz.open(self.pdf_path)
            for page_num, page in enumerate(self.doc):
                text = page.get_text()
                if len(text.strip()) < 50 and use_ocr:
                    text = self._ocr_page(page_num)
                pages.append(text)
            self.log("INFO", f"Extracted text from {len(pages)} pages")
            return pages
        except Exception as exc:
            self.log("ERROR", f"Text extraction failed: {exc}")
            if not use_ocr:
                return self.extract_text(use_ocr=True)
            return pages

    def _ocr_page(self, page_num: int) -> str:
        """OCR a single page (fallback for scanned PDFs)."""
        try:
            images = convert_from_path(self.pdf_path, first_page=page_num + 1, last_page=page_num + 1)
            if images:
                text = pytesseract.image_to_string(images[0])
                self.log("INFO", f"OCR page {page_num + 1}: extracted {len(text)} chars")
                return text
        except Exception as exc:
            self.log("WARN", f"OCR failed for page {page_num + 1}: {exc}")
        return ""

    def log(self, level: str, message: str):
        """Log message for audit trail."""
        self.logs.append({"level": level, "message": message, "timestamp": datetime.utcnow()})
        if level == "ERROR":
            logger.error(message)
        elif level == "WARN":
            logger.warning(message)
        else:
            logger.info(message)

    @abstractmethod
    def parse(self) -> Tuple[Optional[Dict], List[Dict]]:
        """
        Parse PDF and return (statement_metadata, transactions).
        Implemented by subclasses.
        """

    def close(self):
        """Close PDF document."""
        if self.doc:
            self.doc.close()
