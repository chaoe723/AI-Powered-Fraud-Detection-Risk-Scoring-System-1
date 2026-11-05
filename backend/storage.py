"""Storage layer (class 5) for analysis jobs and scored transactions.

SQLite is enough for the KLTN demo; the helpers below are the only surface
the API v1 router uses, so swapping to Postgres later touches only this file.
The database file location can be overridden with ``FRAUD_DB_PATH`` (tests use
this to stay isolated from the demo database).
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import String, cast, delete, func, insert, or_, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _database_url() -> str:
    override = os.getenv("FRAUD_DB_PATH")
    path = Path(override) if override else _REPO_ROOT / "data" / "app.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


_ENGINE: Engine | None = None
_SESSION_FACTORY: sessionmaker | None = None


def get_engine() -> Engine:
    global _ENGINE, _SESSION_FACTORY
    if _ENGINE is None:
        from sqlalchemy import create_engine

        _ENGINE = create_engine(
            _database_url(),
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
        _SESSION_FACTORY = sessionmaker(bind=_ENGINE, expire_on_commit=False)
    return _ENGINE


def get_session_factory() -> sessionmaker:
    get_engine()
    assert _SESSION_FACTORY is not None
    return _SESSION_FACTORY


def reset_engine_for_tests() -> None:
    global _ENGINE, _SESSION_FACTORY
    _ENGINE = None
    _SESSION_FACTORY = None


class Base(DeclarativeBase):
    pass


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    row_count: Mapped[int | None] = mapped_column(default=None)
    processed_rows: Mapped[int] = mapped_column(default=0)
    threshold_profile: Mapped[str] = mapped_column(String(32), default="cost_optimal")
    error: Mapped[str | None] = mapped_column(default=None)
    summary_json: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)


class TransactionRow(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(index=True)
    transaction_id: Mapped[str | None] = mapped_column(String(128), default=None)
    user_id: Mapped[int] = mapped_column(default=1)
    transaction_time: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    amount: Mapped[float] = mapped_column(default=0.0)
    payment_method: Mapped[str] = mapped_column(String(64), default="unknown")
    device: Mapped[str] = mapped_column(String(64), default="unknown")
    country: Mapped[str] = mapped_column(String(64), default="unknown")
    fraud_probability: Mapped[float] = mapped_column(default=0.0)
    anomaly: Mapped[bool] = mapped_column(default=False)
    risk_score: Mapped[float] = mapped_column(default=0.0, index=True)
    risk_level: Mapped[str] = mapped_column(String(16), default="low")
    decision: Mapped[str] = mapped_column(String(32), default="allow")
    reasons_json: Mapped[str] = mapped_column(default="[]")
    raw_json: Mapped[str | None] = mapped_column(default=None)

    __table_args__ = ()  # (analysis_id, risk_level) composite index added below


from sqlalchemy import Index  # noqa: E402  (kept next to the table for clarity)

Index("ix_transactions_analysis_risk", TransactionRow.analysis_id, TransactionRow.risk_level)


def init_db() -> None:
    Base.metadata.create_all(get_engine())


def mark_stale_jobs_failed() -> int:
    """Startup sweep: jobs interrupted by a restart can never resume."""
    factory = get_session_factory()
    with factory() as session:
        result = session.execute(
            update(Analysis)
            .where(Analysis.status.in_(["queued", "processing"]))
            .values(status="failed", error="interrupted by server restart", completed_at=datetime.utcnow())
        )
        session.commit()
        return result.rowcount or 0


def create_analysis(filename: str, threshold_profile: str, row_count: int | None = None) -> int:
    factory = get_session_factory()
    with factory() as session:
        row = Analysis(filename=filename, threshold_profile=threshold_profile, row_count=row_count)
        session.add(row)
        session.commit()
        return int(row.id)


def set_status(analysis_id: int, status: str, *, error: str | None = None, completed: bool = False) -> None:
    factory = get_session_factory()
    with factory() as session:
        values: dict = {"status": status}
        if error is not None:
            values["error"] = error
        if completed:
            values["completed_at"] = datetime.utcnow()
        session.execute(update(Analysis).where(Analysis.id == analysis_id).values(**values))
        session.commit()


def set_processed_rows(analysis_id: int, processed_rows: int) -> None:
    factory = get_session_factory()
    with factory() as session:
        session.execute(update(Analysis).where(Analysis.id == analysis_id).values(processed_rows=processed_rows))
        session.commit()


def bulk_insert_transactions(analysis_id: int, rows: list[dict]) -> None:
    if not rows:
        return
    payload = [{**row, "analysis_id": analysis_id} for row in rows]
    factory = get_session_factory()
    with factory() as session:
        session.execute(insert(TransactionRow), payload)
        session.commit()


def save_summary(analysis_id: int, summary: dict) -> None:
    factory = get_session_factory()
    with factory() as session:
        session.execute(
            update(Analysis).where(Analysis.id == analysis_id).values(summary_json=json.dumps(summary, ensure_ascii=False))
        )
        session.commit()


def get_analysis(analysis_id: int) -> Analysis | None:
    factory = get_session_factory()
    with factory() as session:
        return session.get(Analysis, analysis_id)


def list_analyses(page: int, page_size: int) -> tuple[list[Analysis], int]:
    factory = get_session_factory()
    with factory() as session:
        total = session.scalar(select(func.count()).select_from(Analysis)) or 0
        rows = session.scalars(
            select(Analysis).order_by(Analysis.created_at.desc(), Analysis.id.desc()).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return list(rows), int(total)


def delete_analysis(analysis_id: int) -> bool:
    factory = get_session_factory()
    with factory() as session:
        if session.get(Analysis, analysis_id) is None:
            return False
        session.execute(delete(TransactionRow).where(TransactionRow.analysis_id == analysis_id))
        session.execute(delete(Analysis).where(Analysis.id == analysis_id))
        session.commit()
        return True


_SORT_COLUMNS = {
    "amount": TransactionRow.amount,
    "risk_score": TransactionRow.risk_score,
    "fraud_probability": TransactionRow.fraud_probability,
    "transaction_time": TransactionRow.transaction_time,
}


def query_transactions(
    analysis_id: int,
    *,
    risk_level: str | None = None,
    decision: str | None = None,
    q: str | None = None,
    sort: str = "risk_score",
    order: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[TransactionRow], int]:
    column = _SORT_COLUMNS[sort]
    ordering = column.desc() if order == "desc" else column.asc()
    filters = [TransactionRow.analysis_id == analysis_id]
    if risk_level:
        filters.append(TransactionRow.risk_level == risk_level)
    if decision:
        filters.append(TransactionRow.decision == decision)
    if q:
        like = f"%{q}%"
        filters.append(
            or_(
                TransactionRow.transaction_id.like(like),
                cast(TransactionRow.user_id, String).like(like),
                TransactionRow.country.like(like),
                TransactionRow.device.like(like),
            )
        )
    factory = get_session_factory()
    with factory() as session:
        total = session.scalar(select(func.count()).select_from(TransactionRow).where(*filters)) or 0
        rows = session.scalars(
            select(TransactionRow).where(*filters).order_by(ordering, TransactionRow.id).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return list(rows), int(total)


def get_transaction(analysis_id: int, transaction_id: str) -> TransactionRow | None:
    factory = get_session_factory()
    with factory() as session:
        return session.scalars(
            select(TransactionRow)
            .where(TransactionRow.analysis_id == analysis_id, TransactionRow.transaction_id == transaction_id)
            .order_by(TransactionRow.id)
            .limit(1)
        ).first()


def iter_transactions(analysis_id: int):
    """Yield every scored row of an analysis for export without loading all into RAM."""
    factory = get_session_factory()
    with factory() as session:
        result = session.scalars(select(TransactionRow).where(TransactionRow.analysis_id == analysis_id).order_by(TransactionRow.id))
        for row in result:
            yield row
