"""
AMEX Credit Card Statement Parser
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from fintrack.parsers.base import BaseBankParser

logger = logging.getLogger(__name__)


class AMEXParser(BaseBankParser):
    """AMEX credit card statement parser."""

    ACCOUNT_PATTERN = r"Account Number[:\s]+(\d{4}\s\d{6}\s\d{5}|\d{15})"
    DATE_PATTERN = r"Statement Date[:\s]+([A-Z][a-z]+\s\d{1,2},\s\d{4})"

    def parse(self) -> Tuple[Optional[Dict], List[Dict]]:
        try:
            pages = self.extract_text(use_ocr=False)
            text = "\n".join(pages)

            account_match = re.search(self.ACCOUNT_PATTERN, text)
            account = account_match.group(1).strip() if account_match else "AMEX-UNKNOWN"

            date_match = re.search(self.DATE_PATTERN, text)
            if date_match:
                try:
                    statement_date = datetime.strptime(date_match.group(1), "%B %d, %Y").date()
                except Exception:
                    statement_date = datetime.utcnow().date()
            else:
                statement_date = datetime.utcnow().date()

            statement_meta = {
                "source_type": "credit_card",
                "source_name": "AMEX",
                "account_ref": account,
                "period_start": statement_date.replace(day=1),
                "period_end": statement_date,
                "parse_status": "success",
                "statement_id": self.compute_statement_hash(),
            }

            transactions = self._parse_transactions(text, account, statement_date)
            self.log("INFO", f"Parsed {len(transactions)} AMEX transactions")
            return statement_meta, transactions
        except Exception as exc:
            self.log("ERROR", f"AMEX parse failed: {exc}")
            return None, []
        finally:
            self.close()

    def _parse_transactions(self, text: str, account: str, statement_date) -> List[Dict]:
        transactions = []
        lines = text.split("\n")
        in_section = False
        for line in lines:
            if "Transactions" in line or "Purchases" in line:
                in_section = True
                continue
            if not in_section:
                continue

            line = line.strip()
            if not line or len(line) < 12:
                continue

            match = re.match(r"(\d{2}/\d{2})\s+(.+?)\s+([\d,]+\.\d{2})(?:\s+(C|D|$))?", line)
            if match:
                try:
                    date_str = match.group(1)
                    description = match.group(2).strip()
                    amount = float(match.group(3).replace(",", ""))
                    direction = match.group(4) if match.group(4) else "D"

                    month, day = date_str.split("/")
                    date = datetime(statement_date.year, int(month), int(day)).date()

                    transactions.append({
                        "transaction_date": date,
                        "value_date": None,
                        "description": description,
                        "debit": amount if direction == "D" else None,
                        "credit": amount if direction == "C" else None,
                        "balance": None,
                        "currency": "INR",
                        "raw_line": line,
                    })
                except Exception:
                    continue
        return transactions
