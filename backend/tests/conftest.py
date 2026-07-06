import os
import tempfile

import pytest

# Point the DB + assets at temp dirs BEFORE importing app modules.
_tmp = tempfile.mkdtemp(prefix="openflow_test_")
os.environ["OPENFLOW_DB"] = os.path.join(_tmp, "test.db")
os.environ["OPENFLOW_ASSETS"] = os.path.join(_tmp, "assets")


@pytest.fixture()
def session():
    # Fresh DB per test.
    from app.db import engine, init_db
    from sqlmodel import Session, SQLModel

    SQLModel.metadata.drop_all(engine)
    init_db()
    with Session(engine) as s:
        yield s
