"""
Base PDF Parser with robust text extraction and OCR fallback.
Prefers PyMuPDF (fitz), falls back to pdftotext or pdfminer.six.
OCR via pytesseract+pdf2image when available.
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import shutil

logger = logging.getLogger(__name__)


class BaseBankParser(ABC):
    """Abstract base for bank-specific parsers."""

    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        self.logs: List[Dict] = []

    def compute_statement_hash(self) -> str:
        sha256 = hashlib.sha256()
        with open(self.pdf_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def extract_text(self, use_ocr: bool = False) -> List[str]:
        """Extract text from PDF; optional OCR fallback for scanned pages."""
        pages: List[str] = []

        # Try PyMuPDF
        try:
            import fitz  # type: ignore
            with fitz.open(str(self.pdf_path)) as doc:
                for i, page in enumerate(doc):
                    text = page.get_text() or ""
                    if len(text.strip()) < 50 and use_ocr:
                        text = self._ocr_page(i)
                    pages.append(text)
            self.log("INFO", f"Extracted text via PyMuPDF ({len(pages)} pages)")
            return pages
        except Exception as exc:
            self.log("WARN", f"PyMuPDF unavailable or failed: {exc}")

        # Try pdftotext CLI (poppler-utils)
        if shutil.which("pdftotext"):
            try:
                import subprocess, tempfile
                tmpdir = tempfile.mkdtemp()
                out = Path(tmpdir) / "out.txt"
                subprocess.run(["pdftotext", "-layout", str(self.pdf_path), str(out)], check=True)
                content = out.read_text(errors="ignore")
                pages = [p for p in content.split("\f") if p.strip()] or [content]
                self.log("INFO", f"Extracted text via pdftotext ({len(pages)} pages)")
                if use_ocr and all(len(p.strip()) < 50 for p in pages):
                    pages = [self._ocr_page(i) for i in range(len(pages))]
                return pages
            except Exception as exc:
                self.log("WARN", f"pdftotext failed: {exc}")

        # Try pdfminer.six
        try:
            from pdfminer.high_level import extract_text
            content = extract_text(str(self.pdf_path)) or ""
            pages = [p for p in content.split("\f") if p.strip()] or [content]
            self.log("INFO", f"Extracted text via pdfminer ({len(pages)} pages)")
            if use_ocr and all(len(p.strip()) < 50 for p in pages):
                pages = [self._ocr_page(i) for i in range(len(pages))]
            return pages
        except Exception as exc:
            self.log("ERROR", f"pdfminer failed: {exc}")
            return []

    def _ocr_page(self, page_num: int) -> str:
        """OCR a single page (fallback for scanned PDFs)."""
        try:
            from pdf2image import convert_from_path
            import pytesseract
            images = convert_from_path(str(self.pdf_path), first_page=page_num + 1, last_page=page_num + 1)
            if images:
                text = pytesseract.image_to_string(images[0])
                self.log("INFO", f"OCR page {page_num + 1}: extracted {len(text)} chars")
                return text
        except Exception as exc:
            self.log("WARN", f"OCR failed for page {page_num + 1}: {exc}")
        return ""

    def log(self, level: str, message: str):
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
        raise NotImplementedError
