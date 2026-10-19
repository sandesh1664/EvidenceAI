import uuid
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db import session as session_module
from app.models import User


def test_connection_and_session(db):
    assert db.scalar(text('SELECT 1')) == 1


def test_commit_and_rollback(db):
    email = f'{uuid.uuid4()}@example.test'
    user = User(email=email, display_name='Commit test')
    db.add(user)
    db.commit()
    assert db.scalar(select(User).where(User.email == email)).id == user.id
    db.add(User(email=email, display_name='Duplicate'))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    assert db.scalar(select(User).where(User.email == email)).id == user.id


def test_outer_transaction_removes_committed_records():
    engine = session_module.get_engine()
    identity = uuid.uuid4()
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode='create_savepoint') as session:
            session.add(User(id=identity, email=f'{identity}@example.test', display_name='Isolation'))
            session.commit()
        transaction.rollback()
    with Session(engine) as session:
        assert session.get(User, identity) is None


@pytest.mark.parametrize('fail', [False, True])
def test_dependency_closes_and_rolls_back(monkeypatch, fail):
    events = []
    class FakeSession:
        def __enter__(self): return self
        def __exit__(self, *args): events.append('close')
        def rollback(self): events.append('rollback')
    monkeypatch.setattr(session_module, 'get_session_factory', lambda: FakeSession)
    dependency = session_module.get_db()
    next(dependency)
    if fail:
        with pytest.raises(RuntimeError):
            dependency.throw(RuntimeError('operation failed'))
        assert events == ['rollback', 'close']
    else:
        with pytest.raises(StopIteration): next(dependency)
        assert events == ['close']
