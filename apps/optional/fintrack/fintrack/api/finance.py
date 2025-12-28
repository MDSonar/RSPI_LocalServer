"""
FinTrack Finance API Routes
Endpoints: PDF upload, transaction queries, lineage, exports.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from fintrack.db.database import get_db
from fintrack.db.models import Statement, Transaction, Lineage
from fintrack.workers.ingestor import IngestorService

logger = logging.getLogger(__name__)
router = APIRouter()

# Ensure upload directory exists
UPLOAD_DIR = Path(__file__).parent.parent.parent / "storage" / "pdf_archive"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_statement(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload a bank/credit card statement PDF.
    Auto-detects bank, parses, and ingests transactions.
    Idempotency: uploading the same PDF twice will not duplicate data.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    try:
        pdf_path = UPLOAD_DIR / file.filename
        contents = await file.read()
        pdf_path.write_bytes(contents)

        ingestor = IngestorService(db)
        statement, transactions, issues = ingestor.ingest_pdf(str(pdf_path))

        if not statement:
            detail = issues[0] if issues else "Unknown error"
            raise HTTPException(status_code=400, detail=f"Parse failed: {detail}")

        return {
            "status": "success",
            "statement_id": statement.statement_id,
            "source": statement.source_name,
            "account": statement.account_ref,
            "transactions_ingested": len(transactions),
            "issues": issues,
        }

    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - runtime guard
        logger.error("Upload error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/transactions")
async def list_transactions(
    statement_id: Optional[str] = Query(None),
    source_name: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(100, le=10000),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """
    List transactions with optional filters.
    Query by statement, source, or date range.
    """
    query = db.query(Transaction)

    if statement_id:
        query = query.filter(Transaction.statement_id == statement_id)
    if source_name:
        query = query.filter(Transaction.source_name == source_name)
    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(Transaction.transaction_date >= start)
        except Exception:
            pass
    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(Transaction.transaction_date <= end)
        except Exception:
            pass

    total = query.count()
    transactions = query.order_by(desc(Transaction.transaction_date)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "transactions": [
            {
                "id": t.transaction_id,
                "statement_id": t.statement_id,
                "date": t.transaction_date.isoformat(),
                "description": t.description,
                "debit": float(t.debit) if t.debit else None,
                "credit": float(t.credit) if t.credit else None,
                "balance": float(t.balance) if t.balance else None,
                "source": t.source_name,
            }
            for t in transactions
        ],
    }


@router.get("/lineage/{transaction_id}")
async def get_lineage(transaction_id: str, db: Session = Depends(get_db)):
    """
    Get lineage relationships for a transaction.
    Shows linked transactions (payments, refunds, transfers, duplicates).
    """
    outbound = db.query(Lineage).filter(Lineage.transaction_id == transaction_id).all()
    inbound = db.query(Lineage).filter(Lineage.linked_transaction_id == transaction_id).all()

    return {
        "transaction_id": transaction_id,
        "outbound": [
            {
                "linked_id": entry.linked_transaction_id,
                "type": entry.relationship_type,
                "confidence": entry.confidence,
                "reason": entry.match_reason,
            }
            for entry in outbound
        ],
        "inbound": [
            {
                "source_id": entry.transaction_id,
                "type": entry.relationship_type,
                "confidence": entry.confidence,
                "reason": entry.match_reason,
            }
            for entry in inbound
        ],
    }


@router.get("/statements")
async def list_statements(db: Session = Depends(get_db)):
    """List all ingested statements with metadata."""
    statements = db.query(Statement).order_by(desc(Statement.ingestion_ts)).all()

    return {
        "total": len(statements),
        "statements": [
            {
                "id": stmt.statement_id,
                "source": stmt.source_name,
                "account": stmt.account_ref,
                "period": f"{stmt.period_start.isoformat()} to {stmt.period_end.isoformat()}",
                "status": stmt.parse_status,
                "ingested": stmt.ingestion_ts.isoformat(),
                "transactions": stmt.row_count,
            }
            for stmt in statements
        ],
    }


@router.get("/analytics/summary")
async def analytics_summary(db: Session = Depends(get_db)):
    """Dashboard summary: income, expenses, by source, etc."""
    from sqlalchemy import func
    from decimal import Decimal

    income = db.query(func.sum(Transaction.credit)).scalar() or Decimal(0)
    expenses = db.query(func.sum(Transaction.debit)).scalar() or Decimal(0)

    by_source = db.query(
        Transaction.source_name,
        func.sum(Transaction.debit).label("total_debit"),
        func.sum(Transaction.credit).label("total_credit"),
    ).group_by(Transaction.source_name).all()

    six_months_ago = datetime.now().date() - timedelta(days=180)
    monthly = db.query(
        func.strftime("%Y-%m", Transaction.transaction_date).label("month"),
        func.sum(Transaction.debit).label("expenses"),
        func.sum(Transaction.credit).label("income"),
    ).filter(Transaction.transaction_date >= six_months_ago).group_by("month").order_by("month").all()

    return {
        "total_income": float(income),
        "total_expenses": float(expenses),
        "net": float(income - expenses),
        "by_source": [
            {
                "source": row.source_name,
                "expenses": float(row.total_debit) if row.total_debit else 0,
                "income": float(row.total_credit) if row.total_credit else 0,
            }
            for row in by_source
        ],
        "monthly_trends": [
            {
                "month": row.month,
                "expenses": float(row.expenses) if row.expenses else 0,
                "income": float(row.income) if row.income else 0,
            }
            for row in monthly
        ],
    }


@router.get("/unlinked")
async def get_unlinked_transactions(db: Session = Depends(get_db)):
    """Get transactions with no lineage links."""
    linked_ids = db.query(Lineage.transaction_id).distinct().union(
        db.query(Lineage.linked_transaction_id).distinct()
    )

    unlinked = db.query(Transaction).filter(
        ~Transaction.transaction_id.in_(linked_ids)
    ).order_by(desc(Transaction.transaction_date)).limit(100).all()

    return {
        "count": len(unlinked),
        "transactions": [
            {
                "id": entry.transaction_id,
                "date": entry.transaction_date.isoformat(),
                "description": entry.description,
                "debit": float(entry.debit) if entry.debit else None,
                "credit": float(entry.credit) if entry.credit else None,
                "source": entry.source_name,
            }
            for entry in unlinked
        ],
    }


@router.post("/export-csv")
async def export_csv(db: Session = Depends(get_db)):
    """
    Export all transactions to CSV for archival.
    Older than 6 months are marked for archival.
    """
    import csv
    from io import StringIO

    transactions = db.query(Transaction).order_by(Transaction.transaction_date).all()

    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "transaction_id",
            "statement_id",
            "date",
            "description",
            "debit",
            "credit",
            "balance",
            "source_name",
            "currency",
        ],
    )
    writer.writeheader()
    for txn in transactions:
        writer.writerow({
            "transaction_id": txn.transaction_id,
            "statement_id": txn.statement_id,
            "date": txn.transaction_date.isoformat(),
            "description": txn.description,
            "debit": float(txn.debit) if txn.debit else "",
            "credit": float(txn.credit) if txn.credit else "",
            "balance": float(txn.balance) if txn.balance else "",
            "source_name": txn.source_name,
            "currency": txn.currency,
        })

    export_path = Path(__file__).parent.parent.parent / "storage" / "csv_export" / f"fintrack-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(output.getvalue())

    return {
        "status": "success",
        "file": str(export_path),
        "transaction_count": len(transactions),
    }


@router.post("/archive")
async def archive_transactions(days_old: int = Query(180, ge=30, le=730)):
    """Archive transactions older than `days_old` to monthly CSV files."""
    from fintrack.workers.archive import archive_old_transactions

    result = archive_old_transactions(days_old=days_old)

    if result["errors"]:
        logger.error("Archive errors: %s", result["errors"])

    return {
        "status": "success" if not result["errors"] else "partial",
        "exported": result["exported"],
        "manifest": result["manifest_file"],
        "errors": result["errors"],
    }


@router.post("/restore-archive")
async def restore_from_archive(csv_file: str = Query(...)):
    """Restore transactions from archived CSV back to SQLite."""
    from fintrack.workers.archive import restore_from_archive

    result = restore_from_archive(Path(csv_file))

    if result["errors"]:
        logger.error("Restore errors: %s", result["errors"])

    return {
        "status": "success" if not result["errors"] else "partial",
        "restored": result["restored"],
        "errors": result["errors"],
    }
