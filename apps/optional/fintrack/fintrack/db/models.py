"""
FinTrack SQLAlchemy Models
Represents core finance data: statements, transactions, relationships, and audit logs.
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Date, Float, Integer, ForeignKey, Numeric, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Statement(Base):
    """Tracks statement provenance and idempotency."""

    __tablename__ = "statements"

    statement_id = Column(String(64), primary_key=True)
    source_type = Column(String(20), nullable=False)
    source_name = Column(String(50), nullable=False)
    account_ref = Column(String(50), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    ingestion_ts = Column(DateTime, default=datetime.utcnow, nullable=False)
    parse_status = Column(String(20), nullable=False)
    pdf_path = Column(String(255), nullable=True)
    page_count = Column(Integer, nullable=True)
    row_count = Column(Integer, nullable=True)

    transactions = relationship("Transaction", back_populates="statement", cascade="all, delete-orphan")
    logs = relationship("IngestionLog", back_populates="statement", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_statement_source_period", "source_name", "period_start", "period_end"),
        Index("idx_statement_account", "source_type", "account_ref"),
    )


class Transaction(Base):
    """Normalized transaction store."""

    __tablename__ = "transactions"

    transaction_id = Column(String(64), primary_key=True)
    statement_id = Column(String(64), ForeignKey("statements.statement_id"), nullable=False)
    transaction_date = Column(Date, nullable=False)
    value_date = Column(Date, nullable=True)
    description = Column(Text, nullable=False)
    debit = Column(Numeric(12, 2), nullable=True)
    credit = Column(Numeric(12, 2), nullable=True)
    balance = Column(Numeric(12, 2), nullable=True)
    currency = Column(String(3), default="INR", nullable=False)
    source_type = Column(String(20), nullable=False)
    source_name = Column(String(50), nullable=False)
    raw_line = Column(Text, nullable=True)
    created_ts = Column(DateTime, default=datetime.utcnow, nullable=False)

    statement = relationship("Statement", back_populates="transactions")
    outbound_links = relationship(
        "Lineage",
        foreign_keys="Lineage.transaction_id",
        back_populates="source_transaction",
        cascade="all, delete-orphan",
    )
    inbound_links = relationship(
        "Lineage",
        foreign_keys="Lineage.linked_transaction_id",
        back_populates="linked_transaction",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_transaction_date", "transaction_date"),
        Index("idx_transaction_statement", "statement_id"),
        Index("idx_transaction_debit_credit", "debit", "credit"),
        Index("idx_transaction_account", "source_type", "source_name"),
    )


class Lineage(Base):
    """Tracks financial relationships between transactions."""

    __tablename__ = "lineage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String(64), ForeignKey("transactions.transaction_id"), nullable=False)
    linked_transaction_id = Column(String(64), ForeignKey("transactions.transaction_id"), nullable=False)
    relationship_type = Column(String(30), nullable=False)
    confidence = Column(Float, default=0.0, nullable=False)
    match_reason = Column(Text, nullable=True)
    created_ts = Column(DateTime, default=datetime.utcnow, nullable=False)

    source_transaction = relationship(
        "Transaction",
        foreign_keys=[transaction_id],
        back_populates="outbound_links",
    )
    linked_transaction = relationship(
        "Transaction",
        foreign_keys=[linked_transaction_id],
        back_populates="inbound_links",
    )

    __table_args__ = (
        Index("idx_lineage_source", "transaction_id"),
        Index("idx_lineage_linked", "linked_transaction_id"),
        Index("idx_lineage_type_confidence", "relationship_type", "confidence"),
    )


class IngestionLog(Base):
    """Audit trail for debugging and compliance."""

    __tablename__ = "ingestion_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    statement_id = Column(String(64), ForeignKey("statements.statement_id"), nullable=False)
    level = Column(String(10), nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    statement = relationship("Statement", back_populates="logs")

    __table_args__ = (
        Index("idx_log_statement", "statement_id"),
        Index("idx_log_level", "level"),
        Index("idx_log_timestamp", "timestamp"),
    )
