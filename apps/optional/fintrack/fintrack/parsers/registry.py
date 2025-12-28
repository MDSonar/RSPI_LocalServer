"""
Parser registry and autodetection
"""

import logging
import re
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from fintrack.parsers.base import BaseBankParser
from fintrack.parsers.sbi import SBIParser
from fintrack.parsers.hdfc import HDFCParser
from fintrack.parsers.amex import AMEXParser

logger = logging.getLogger(__name__)


def detect_bank(pdf_text: str) -> Optional[str]:
    text_lower = pdf_text.lower()
    if re.search(r"state bank of india|sbi", text_lower):
        return "SBI"
    if re.search(r"hdfc bank|hdfc\s+bank", text_lower):
        return "HDFC"
    if re.search(r"american express|amex|credit card statement", text_lower):
        return "AMEX"
    return None


def get_parser(pdf_path: str) -> Optional[BaseBankParser]:
    try:
        import fitz

        doc = fitz.open(pdf_path)
        first_page = doc[0].get_text() if doc else ""
        doc.close()

        bank = detect_bank(first_page)

        if bank == "SBI":
            return SBIParser(pdf_path)
        if bank == "HDFC":
            return HDFCParser(pdf_path)
        if bank == "AMEX":
            return AMEXParser(pdf_path)

        logger.error("Unknown bank/card type in PDF: %s", pdf_path)
        return None
    except Exception as exc:
        logger.error("Error detecting bank for %s: %s", pdf_path, exc)
        return None


def parse_pdf(pdf_path: str) -> Tuple[Optional[Dict], List[Dict], List[Dict]]:
    parser = get_parser(pdf_path)
    if not parser:
        return None, [], [{"level": "ERROR", "message": "Unsupported bank/card type"}]

    statement_meta, transactions = parser.parse()
    logs = parser.logs
    return statement_meta, transactions, logs
