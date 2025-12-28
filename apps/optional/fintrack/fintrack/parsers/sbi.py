"""
SBI Bank Statement Parser
"""

import logging
import re
from datetime import datetime
from typing import Optional, List, Dict, Tuple

from fintrack.parsers.base import BaseBankParser

logger = logging.getLogger(__name__)


class SBIParser(BaseBankParser):
    """SBI Bank statement parser."""

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

            self.log("INFO", f"Parsed {len(transactions)} transactions from SBI statement")
            return statement_meta, transactions

        except Exception as exc:
            self.log("ERROR", f"SBI parse failed: {exc}")
            return None, []
        finally:
            self.close()

    def _extract_statement_meta(self, pages: List[str]) -> Optional[Dict]:
        if not pages:
            return None

        first_page = pages[0]

        account_match = re.search(r"(\*{5}\d{4}|[A-Z0-9]{10,})", first_page, re.IGNORECASE)
        self.account_ref = account_match.group(1) if account_match else "UNKNOWN"

        period_match = re.search(
            r"(\d{1,2}[-/](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[A-Za-z]*[-/](\d{4}))\s+to\s+(\d{1,2}[-/](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[A-Za-z]*[-/](\d{4}))",
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
            "source_name": "SBI",
            "account_ref": self.account_ref,
            "period_start": period_start,
            "period_end": period_end,
            "parse_status": "success",
        }

    def _extract_transactions(self, pages: List[str]) -> List[Dict]:
        transactions = []
        transaction_pattern = re.compile(
            r"^(\d{1,2}[-/](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[A-Za-z]*[-/](\d{4}))\s+(.+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)$",
            re.MULTILINE | re.IGNORECASE,
        )

        for page in pages:
            lines = page.split("\n")
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if not line or len(line) < 10:
                    i += 1
                    continue

                match = transaction_pattern.match(line)
                if match:
                    trans_date = self._parse_date(match.group(1))
                    description = match.group(3).strip()
                    debit_str = match.group(4).replace(",", "")
                    credit_str = match.group(5).replace(",", "")
                    balance_str = match.group(6).replace(",", "")

                    i += 1
                    while i < len(lines):
                        next_line = lines[i].strip()
                        if not next_line or transaction_pattern.match(next_line):
                            break
                        description += " " + next_line
                        i += 1

                    trans = {
                        "transaction_date": trans_date,
                        "value_date": None,
                        "description": description,
                        "debit": self._safe_float(debit_str) if debit_str else None,
                        "credit": self._safe_float(credit_str) if credit_str else None,
                        "balance": self._safe_float(balance_str) if balance_str else None,
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

    def _parse_date(self, date_str: str) -> datetime:
        formats = ["%d-%b-%Y", "%d-%B-%Y", "%d/%m/%Y", "%d-%m-%Y", "%d-%m-%y"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except Exception:
                pass
        self.log("WARN", f"Could not parse date: {date_str}")
        return datetime.now().date()

    def _safe_float(self, value: str) -> Optional[float]:
        if not value or value in {"0", "0.00"}:
            return None
        try:
            return float(value.replace(",", ""))
        except Exception:
            return None
