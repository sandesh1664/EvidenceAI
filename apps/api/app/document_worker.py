"""Start with python -m app.document_worker; use --once for a single bounded tick."""
import argparse
import logging
import signal
import threading
import os
from pathlib import Path
import tempfile
import time
from app.core.telemetry import configure_logging, measured, registry, emit

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.services.document_jobs import run_once
from app.services.document_storage import get_document_storage


def main():
    parser = argparse.ArgumentParser(description='EvidenceAI durable document worker')
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--metrics-file', type=Path, help='Atomic Prometheus textfile (private operator directory)')
    args = parser.parse_args()
    configure_logging()
    settings, factory = get_settings(), get_session_factory()
    if args.status:
        from app.operations import main as diagnostics
        import sys
        sys.argv = [sys.argv[0]]
        diagnostics()
        return
    storage, stop = get_document_storage(), threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    tick = measured('worker_tick')(run_once)
    emit('worker_started')
    while not stop.is_set():
        try:
            with factory() as db:
                worked = tick(db,settings,storage)
        except Exception:
            # No SQL, paths, filenames, extracted text, tokens or credentials in logs.
            logging.error('Document worker tick failed; uncommitted work rolled back')
            if args.once:
                raise SystemExit(1) from None
            worked = False
        if args.metrics_file:
            try:
                write_metrics(args.metrics_file)
            except OSError:
                emit('worker_metrics_failed',error_category='storage')
        if args.once:
            return
        if not worked:
            stop.wait(1)

    emit('worker_stopped')


def write_metrics(path):
    # Operator chooses an existing directory; atomic replacement prevents partial scrapes.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
            temporary = stream.name
            stream.write(registry.render())
            stream.write('# HELP evidenceai_worker_last_tick_timestamp_seconds Unix timestamp of last completed worker tick.\n# TYPE evidenceai_worker_last_tick_timestamp_seconds gauge\n')
            stream.write(f'evidenceai_worker_last_tick_timestamp_seconds {time.time()}\n')
        os.chmod(temporary,0o640)
        os.replace(temporary,path)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


if __name__ == '__main__':
    main()
