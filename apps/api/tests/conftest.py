"""Each database test owns an outer transaction; session commits use savepoints."""
import pytest
from sqlalchemy.orm import Session
from app.db.session import get_engine


@pytest.fixture
def connection():
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()


@pytest.fixture
def db(connection):
    with Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False) as session:
        yield session
