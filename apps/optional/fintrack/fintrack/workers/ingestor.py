"""
Transaction Ingestion Service
"""

import hashlib
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from fintrack.db.models import Statement, Transaction, Lineage, IngestionLog
from fintrack.parsers.registry import parse_pdf

logger = logging.getLogger(__name__)


class IngestorService:
    """Manages PDF ingestion with idempotency and lineage detection."""

    def __init__(self, db: Session):
        self.db = db

    def ingest_pdf(self, pdf_path: str) -> Tuple[Optional[Dict], List[Dict], List[str]]:
        statement_meta, transactions, parse_logs = parse_pdf(pdf_path)

        if not statement_meta:
            issue = "Failed to parse PDF: unsupported bank/card type"
            logger.error(issue)
            return None, [], [issue]

        statement_id = statement_meta["statement_id"]

        existing = self.db.query(Statement).filter(Statement.statement_id == statement_id).first()
        if existing:
            msg = f"Statement {statement_id} already ingested (duplicate PDF)"
            logger.info(msg)
            return existing, [], [msg]

        try:
            statement = Statement(
                statement_id=statement_id,
                source_type=statement_meta["source_type"],
                source_name=statement_meta["source_name"],
                account_ref=statement_meta["account_ref"],
                period_start=statement_meta["period_start"],
                period_end=statement_meta["period_end"],
                parse_status=statement_meta.get("parse_status", "success"),
                pdf_path=str(pdf_path),
                page_count=len(parse_logs),
                row_count=len(transactions),
                ingestion_ts=datetime.utcnow(),
            )
            self.db.add(statement)
            self.db.flush()

            issues: List[str] = []
            inserted_transactions: List[Transaction] = []
            for trans_data in transactions:
                trans_id = self._compute_transaction_hash(statement_id, trans_data)
                try:
                    trans = Transaction(
                        transaction_id=trans_id,
                        statement_id=statement_id,
                        transaction_date=trans_data["transaction_date"],
                        value_date=trans_data.get("value_date"),
                        description=trans_data["description"],
                        debit=Decimal(str(trans_data["debit"])) if trans_data.get("debit") else None,
                        credit=Decimal(str(trans_data["credit"])) if trans_data.get("credit") else None,
                        balance=Decimal(str(trans_data["balance"])) if trans_data.get("balance") else None,
                        currency=trans_data.get("currency", "INR"),
                        source_type=statement_meta["source_type"],
                        source_name=statement_meta["source_name"],
                        raw_line=trans_data.get("raw_line"),
                        created_ts=datetime.utcnow(),
                    )
                    inserted_transactions.append(trans)
                    self.db.add(trans)
                except Exception as exc:
                    issues.append(f"Failed to insert transaction: {exc}")
                    logger.warning("Transaction insert failed: %s", exc)

            self._detect_lineage(statement_id, inserted_transactions)

            for log in parse_logs:
                log_entry = IngestionLog(
                    statement_id=statement_id,
                    level=log.get("level", "INFO"),
                    message=log.get("message", ""),
                    timestamp=log.get("timestamp", datetime.utcnow()),
                )
                self.db.add(log_entry)

            self.db.commit()
            logger.info("Ingested %s transactions from %s", len(transactions), statement_meta["source_name"])
            return statement, transactions, issues

        except Exception as exc:
            self.db.rollback()
            logger.error("Ingestion failed: %s", exc)
            return None, [], [str(exc)]

    def _compute_transaction_hash(self, statement_id: str, trans_data: Dict) -> str:
        key = f"{statement_id}|{trans_data['transaction_date']}|{trans_data['description']}|{trans_data.get('debit', '')}|{trans_data.get('credit', '')}"
        return hashlib.sha256(key.encode()).hexdigest()

    def _detect_lineage(self, statement_id: str, transactions: List[Transaction]):
        existing = self.db.query(Transaction).filter(Transaction.source_name.in_(["SBI", "HDFC", "AMEX"])).all()

        for trans in transactions:
            trans_date = trans.transaction_date
            amount = trans.debit or trans.credit
            description = trans.description

            for existing_trans in existing:
                if existing_trans.statement_id == statement_id:
                    continue

                if (
                    trans.debit
                    and existing_trans.credit
                    and abs(float(trans.debit) - float(existing_trans.credit)) < 0.01
                    and abs((trans_date - existing_trans.transaction_date).days) <= 2
                ):
                    lineage = Lineage(
                        transaction_id=existing_trans.transaction_id,
                        linked_transaction_id=trans.transaction_id,
                        relationship_type="cc_payment",
                        confidence=0.95,
                        match_reason=f"CC bill payment: {existing_trans.source_name} credit matches {trans.source_name} debit",
                    )
                    self.db.add(lineage)

                if (
                    trans.credit
                    and existing_trans.debit
                    and abs(float(trans.credit) - float(existing_trans.debit)) < 0.01
                    and abs((trans_date - existing_trans.transaction_date).days) <= 30
                    and self._description_similarity(description, existing_trans.description) > 0.7
                ):
                    lineage = Lineage(
                        transaction_id=existing_trans.transaction_id,
                        linked_transaction_id=trans.transaction_id,
                        relationship_type="refund",
                        confidence=0.8,
                        match_reason="Possible refund: debit reversed as credit",
                    )
                    self.db.add(lineage)

        self.db.flush()

    def _description_similarity(self, desc1: str, desc2: str) -> float:
        words1 = set(desc1.lower().split())
        words2 = set(desc2.lower().split())
        if not words1 or not words2:
            return 0.0
        overlap = len(words1 & words2)
        total = len(words1 | words2)
        return overlap / total if total > 0 else 0.0
