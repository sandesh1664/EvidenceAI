"""Database-wide generation slots, without persistent records or long transactions."""

from contextlib import contextmanager

from sqlalchemy import func, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import TimeoutError as PoolTimeout

# Session-scoped advisory locks shared by application workers on the same DB.
NAMESPACE = 1162428743


class CapacityBusy(Exception):
    pass


@contextmanager
def generation_slot(db, settings):
    bind = db.get_bind()
    engine = bind.engine if isinstance(bind, Connection) else bind
    try:
        connection = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    except PoolTimeout:
        raise CapacityBusy() from None
    slot = None
    try:
        for candidate in range(settings.rag_concurrent_generations):
            if connection.scalar(
                select(func.pg_try_advisory_lock(NAMESPACE, candidate))
            ):
                slot = candidate
                break
        if slot is None:
            raise CapacityBusy()
        yield
    finally:
        if slot is not None:
            try:
                unlocked = connection.scalar(
                    select(func.pg_advisory_unlock(NAMESPACE, slot))
                )
                if not unlocked:
                    connection.invalidate()
            except Exception:  # noqa: BLE001 - discard any session whose unlock failed
                # Returning a session with a held advisory lock to the pool is unsafe.
                connection.invalidate()
        connection.close()
