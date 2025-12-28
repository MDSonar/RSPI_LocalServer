"""
CSV cold archival worker for FinTrack
"""

import csv
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from fintrack.db.database import SessionLocal
from fintrack.db.models import Transaction

logger = logging.getLogger(__name__)

ARCHIVE_PATH = Path(__file__).parent.parent / "storage" / "csv_export"
ARCHIVE_PATH.mkdir(parents=True, exist_ok=True)

MIN_ARCHIVE_DAYS = 180


def archive_old_transactions(days_old: int = MIN_ARCHIVE_DAYS) -> dict:
    db = SessionLocal()
    errors = []
    exported_count = 0

    try:
        cutoff_date = datetime.utcnow().date() - timedelta(days=days_old)
        transactions = db.query(Transaction).filter(Transaction.transaction_date < cutoff_date).all()

        if not transactions:
            logger.info("No transactions to archive")
            return {"exported": 0, "manifest_file": None, "errors": []}

        by_month = {}
        for txn in transactions:
            month_key = txn.transaction_date.strftime("%Y-%m")
            by_month.setdefault(month_key, []).append(txn)

        manifest_entries = []
        for month_key, txns in by_month.items():
            try:
                filename = f"{month_key}-transactions.csv"
                filepath = ARCHIVE_PATH / filename

                with open(filepath, "w", newline="") as handle:
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=[
                            "transaction_id",
                            "date",
                            "description",
                            "debit",
                            "credit",
                            "balance",
                            "source_name",
                            "statement_id",
                        ],
                    )
                    writer.writeheader()
                    for txn in txns:
                        writer.writerow({
                            "transaction_id": txn.transaction_id,
                            "date": txn.transaction_date.isoformat(),
                            "description": txn.description,
                            "debit": float(txn.debit) if txn.debit else "",
                            "credit": float(txn.credit) if txn.credit else "",
                            "balance": float(txn.balance) if txn.balance else "",
                            "source_name": txn.source_name,
                            "statement_id": txn.statement_id,
                        })

                manifest_entries.append({
                    "month": month_key,
                    "file": filename,
                    "count": len(txns),
                    "archived_at": datetime.utcnow().isoformat(),
                })
                exported_count += len(txns)
                logger.info("Archived %s txns to %s", len(txns), filename)

            except Exception as exc:
                error_msg = f"Failed to archive {month_key}: {exc}"
                logger.error(error_msg)
                errors.append(error_msg)

        manifest_file = ARCHIVE_PATH / "archive_manifest.json"
        try:
            manifest_data = {
                "created_at": datetime.utcnow().isoformat(),
                "cutoff_days": days_old,
                "entries": manifest_entries,
            }
            with open(manifest_file, "w") as handle:
                json.dump(manifest_data, handle, indent=2)
        except Exception as exc:
            error_msg = f"Failed to write manifest: {exc}"
            logger.error(error_msg)
            errors.append(error_msg)

        return {
            "exported": exported_count,
            "manifest_file": str(manifest_file),
            "errors": errors,
        }

    finally:
        db.close()


def restore_from_archive(csv_file: Path) -> dict:
    db = SessionLocal()
    errors = []
    restored_count = 0

    try:
        if not csv_file.exists():
            return {"restored": 0, "errors": [f"CSV file not found: {csv_file}"]}

        with open(csv_file, "r") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                try:
                    existing = db.query(Transaction).filter(Transaction.transaction_id == row["transaction_id"]).first()
                    if existing:
                        logger.debug("Transaction %s already exists", row["transaction_id"])
                        continue

                    txn = Transaction(
                        transaction_id=row["transaction_id"],
                        statement_id=row["statement_id"],
                        transaction_date=datetime.fromisoformat(row["date"]).date(),
                        description=row["description"],
                        debit=float(row["debit"]) if row.get("debit") else None,
                        credit=float(row["credit"]) if row.get("credit") else None,
                        balance=float(row["balance"]) if row.get("balance") else None,
                        source_name=row.get("source_name", ""),
                        source_type="unknown",
                        currency="INR",
                        created_ts=datetime.utcnow(),
                    )
                    db.add(txn)
                    restored_count += 1

                except Exception as exc:
                    error_msg = f"Failed to restore row {row.get('transaction_id')}: {exc}"
                    logger.error(error_msg)
                    errors.append(error_msg)

        db.commit()
        logger.info("Restored %s transactions from %s", restored_count, csv_file)
        return {"restored": restored_count, "errors": errors}

    except Exception as exc:
        db.rollback()
        error_msg = f"Restore failed: {exc}"
        logger.error(error_msg)
        return {"restored": 0, "errors": [error_msg]}

    finally:
        db.close()
