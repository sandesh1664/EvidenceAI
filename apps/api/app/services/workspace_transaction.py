from contextlib import contextmanager

from fastapi import HTTPException
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session


@contextmanager
def workspace_transaction(db: Session):
    """Use Session autobegin; also works inside externally owned test transactions."""
    try:
        yield
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Operation conflicts with workspace data") from None
    except DBAPIError as error:
        db.rollback()
        if getattr(error.orig, "sqlstate", None) in {"40001", "40P01", "55P03"}:
            raise HTTPException(409, "Concurrent workspace change; retry request") from None
        raise
    except Exception:
        db.rollback()
        raise
