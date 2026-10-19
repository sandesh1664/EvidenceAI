"""Start with python -m app.document_worker; use --once for a single bounded tick."""
import argparse
import logging
import signal
import threading

from sqlalchemy import func, select
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import DocumentJob, StorageCleanup, EmbeddingJob
from app.services.document_jobs import run_once
from app.services.document_storage import get_document_storage


def main():
    parser = argparse.ArgumentParser(description='EvidenceAI durable document worker')
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    settings, factory = get_settings(), get_session_factory()
    if args.status:
        with factory() as db:
            print(dict(db.execute(select(DocumentJob.state,func.count()).group_by(DocumentJob.state)).all()))
            print('embedding_jobs:',dict(db.execute(select(EmbeddingJob.state,func.count()).group_by(EmbeddingJob.state)).all()))
            print('cleanup_pending:',db.scalar(select(func.count()).select_from(StorageCleanup)))
        return
    storage, stop = get_document_storage(), threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
    while not stop.is_set():
        try:
            with factory() as db:
                worked = run_once(db,settings,storage)
        except Exception:
            # No SQL, paths, filenames, extracted text, tokens or credentials in logs.
            logging.error('Document worker tick failed; uncommitted work rolled back')
            if args.once:
                raise SystemExit(1) from None
            worked = False
        if args.once:
            return
        if not worked:
            stop.wait(1)


if __name__ == '__main__':
    main()
