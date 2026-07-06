import os
from contextlib import contextmanager

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

DB_PATH = os.environ.get("OPENFLOW_DB", os.path.join(os.path.dirname(__file__), "..", "openflow.db"))
ASSETS_DIR = os.path.abspath(os.environ.get("OPENFLOW_ASSETS", os.path.join(os.path.dirname(__file__), "..", "..", "assets")))

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False, "timeout": 30})


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=30000")
    cur.close()


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    for sub in ("refs", "clips", "exports", "frames"):
        os.makedirs(os.path.join(ASSETS_DIR, sub), exist_ok=True)


def get_session():
    with Session(engine) as session:
        yield session


@contextmanager
def immediate_session():
    """Session opening a BEGIN IMMEDIATE transaction — used by /queue/claim to
    prevent two workers double-claiming the same job on SQLite."""
    with Session(engine) as session:
        session.connection().exec_driver_sql("BEGIN IMMEDIATE") if not session.in_transaction() else None
        yield session
