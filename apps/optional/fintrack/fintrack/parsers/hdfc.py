"""
HDFC Bank Statement Parser
"""

import logging
import re
from datetime import datetime
from typing import Optional, List, Dict, Tuple

from fintrack.parsers.base import BaseBankParser

logger = logging.getLogger(__name__)


class HDFCParser(BaseBankParser):
    """HDFC Bank statement parser."""

    def __init__(self, pdf_path: str):
        super().__init__(pdf_path)
        self.account_ref = None
        self.period_start = None
        self.period_end = None

    def parse(self) -> Tuple[Optional[Dict], List[Dict]]:
        try:
            pages = self.extract_text(use_ocr=False)
            statement_meta = self._extract_statement_meta(pages)
            transactions = self._extract_transactions(pages)

            if not statement_meta:
                self.log("ERROR", "Could not extract statement metadata")
                return None, transactions

            statement_meta["parse_status"] = "success" if transactions else "partial"
            statement_meta["statement_id"] = self.compute_statement_hash()

            self.log("INFO", f"Parsed {len(transactions)} transactions from HDFC statement")
            return statement_meta, transactions

        except Exception as exc:
            self.log("ERROR", f"HDFC parse failed: {exc}")
            return None, []
        finally:
            self.close()

    def _extract_statement_meta(self, pages: List[str]) -> Optional[Dict]:
        if not pages:
            return None

        first_page = pages[0]

        account_match = re.search(r"(\*{5}\d{4}|50\d{8})", first_page)
        self.account_ref = account_match.group(1) if account_match else "UNKNOWN"

        period_match = re.search(
            r"(\d{1,2}[-/](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[A-Za-z]*[-/](\d{4}))\s+(?:to|–)\s+(\d{1,2}[-/](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[A-Za-z]*[-/](\d{4}))",
            first_page,
            re.IGNORECASE,
        )

        if period_match:
            try:
                period_start = self._parse_date(period_match.group(1))
                period_end = self._parse_date(period_match.group(3))
            except Exception:
                period_start = period_end = datetime.now().date()
        else:
            period_start = period_end = datetime.now().date()

        return {
            "source_type": "bank",
            "source_name": "HDFC",
            "account_ref": self.account_ref,
            "period_start": period_start,
            "period_end": period_end,
            "parse_status": "success",
        }

    def _extract_transactions(self, pages: List[str]) -> List[Dict]:
        transactions = []

        for page in pages:
            lines = page.split("\n")
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if not line or len(line) < 10:
                    i += 1
                    continue

                match = re.match(
                    r"^(\d{1,2}[-/](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[A-Za-z]*[-/]\d{2,4})\s+(.+?)\s+([\d,]+\.?\d*)\s*([\d,]+\.?\d*)\s*([\d,]+\.?\d*)?$",
                    line,
                    re.IGNORECASE,
                )

                if match:
                    trans_date = self._parse_date(match.group(1))
                    description = match.group(2).strip()
                    amount1 = match.group(3).replace(",", "")
                    amount2 = match.group(4).replace(",", "")
                    balance = match.group(5).replace(",", "") if match.group(5) else None

                    debit, credit = self._infer_debit_credit(amount1, amount2)

                    i += 1
                    while i < len(lines):
                        next_line = lines[i].strip()
                        if not next_line or re.match(r"^\d{1,2}[-/]", next_line):
                            break
                        description += " " + next_line
                        i += 1

                    trans = {
                        "transaction_date": trans_date,
                        "value_date": None,
                        "description": description,
                        "debit": debit,
                        "credit": credit,
                        "balance": self._safe_float(balance) if balance else None,
                        "currency": "INR",
                        "raw_line": line,
                    }
                    transactions.append(trans)
                else:
                    i += 1

        seen = set()
        unique = []
        for trans in transactions:
            key = (trans["transaction_date"], trans["description"], trans["debit"], trans["credit"])
            if key not in seen:
                seen.add(key)
                unique.append(trans)

        return unique

    def _infer_debit_credit(self, amount1: str, amount2: str) -> Tuple[Optional[float], Optional[float]]:
        try:
            a1 = float(amount1) if amount1 else 0
            a2 = float(amount2) if amount2 else 0
            if a1 > 0 and a2 == 0:
                return a1, None
            if a2 > 0 and a1 == 0:
                return None, a2
            if a1 > 0:
                return a1, None
            if a2 > 0:
                return None, a2
        except Exception:
            pass
        return None, None

    def _parse_date(self, date_str: str) -> datetime:
        formats = ["%d-%b-%y", "%d-%B-%y", "%d-%b-%Y", "%d-%B-%Y", "%d/%m/%Y", "%d/%m/%y"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except Exception:
                pass
        self.log("WARN", f"Could not parse HDFC date: {date_str}")
        return datetime.now().date()

    def _safe_float(self, value: str) -> Optional[float]:
        if not value or value in {"0", "0.00"}:
            return None
        try:
            return float(value.replace(",", ""))
        except Exception:
            return None
