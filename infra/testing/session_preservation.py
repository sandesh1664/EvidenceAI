#!/usr/bin/env python3
"""Read-only DB preservation with private keyed session-column fingerprints.

No private storage files are accessed. This complements, never replaces, the
original strict storage/table preservation receipts. Keys and snapshots stay outside Git.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import stat

from sqlalchemy import text
from preservation import TABLES

ROOT = Path(__file__).resolve().parents[2]
ORDERS = {'auth_rate_limits':'key,window_start','document_jobs':'document_id',
          'storage_cleanup':'storage_key','chunk_embeddings':'chunk_id,profile_id',
          'embedding_jobs':'document_id,profile_id'}


def private_path(path):
    path = Path(path).absolute()
    if path.resolve() == ROOT or ROOT in path.resolve().parents:
        raise ValueError('Private evidence must remain outside the repository')
    info = path.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('An owned mode-0700 evidence directory is required')
    return path


def write_private(path, value, binary=False):
    path = private_path(path)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb' if binary else 'w') as stream:
        stream.write(value if binary else json.dumps(value, indent=2)+'\n')


def read_private(path, binary=False):
    path = private_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb' if binary else 'r') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError('Private evidence must be an owned mode-0600 regular file')
        return stream.read() if binary else json.load(stream)


def fingerprint(key, domain, value):
    payload = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hmac.new(key, (domain+'\0'+payload).encode(), hashlib.sha256).hexdigest()


def capture(engine, key):
    state = {'format_version':1, 'key_id':hashlib.sha256(key).hexdigest(),
             'captured_at':datetime.now(timezone.utc).isoformat(), 'tables':{},
             'storage_scope':'NOT INSPECTED; no private-document/file access'}
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        connection.execute(text("SET LOCAL statement_timeout = '15000ms'"))
        state['transaction'] = {name:connection.scalar(text('SHOW '+name)) for name in
                                ('transaction_isolation','transaction_read_only','TimeZone','server_version')}
        state['database_identity'] = fingerprint(key, 'database',
            [engine.url.host, engine.url.port, engine.url.database])
        for table in TABLES:
            order = ORDERS.get(table, 'id')
            # Only aggregate digests leave PostgreSQL; document/chunk bodies never
            # enter this process. Matches the original tool's exact row serialization.
            row = connection.execute(text(f"""SELECT count(*) AS count,
                encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t)::text,
                E'\\n' ORDER BY {order}), ''), 'UTF8')), 'hex') AS hash
                FROM public.{table} t""")).mappings().one()
            state['tables'][table] = dict(row)
        state['revision'] = connection.scalar(text('SELECT version_num FROM public.alembic_version'))
        sessions = connection.scalars(text('SELECT to_jsonb(t) FROM public.auth_sessions t ORDER BY id')).all()
        state['sessions'] = session_fingerprints(sessions, key)
    return state


def session_fingerprints(rows, key):
    return {fingerprint(key, 'session-id', row['id']):
            {column:fingerprint(key, 'column:'+column, value) for column,value in row.items()}
            for row in rows}


def compare(before, after):
    for name in ('format_version','key_id','database_identity'):
        if before[name] != after[name]:
            raise ValueError('Incompatible evidence context')
    tables = {name:{'count_delta':after['tables'][name]['count']-before['tables'][name]['count'],
                    'hash_changed':after['tables'][name]['hash'] != before['tables'][name]['hash']}
              for name in TABLES if before['tables'][name] != after['tables'][name]}
    old, new = before['sessions'], after['sessions']
    changed = []
    for alias in sorted(old.keys() & new.keys()):
        columns = sorted(name for name in old[alias].keys() | new[alias].keys()
                         if old[alias].get(name) != new[alias].get(name))
        if columns:
            changed.append({'private_row_alias':'session-'+alias[:16], 'columns':columns})
    equal = not tables and before['revision'] == after['revision'] and not changed and old.keys() == new.keys()
    return {'status':'PASS' if equal else 'FAIL', 'changed_tables':tables,
            'changed_sessions':changed, 'sessions_added':len(new.keys()-old.keys()),
            'sessions_removed':len(old.keys()-new.keys()), 'revision_equal':before['revision']==after['revision'],
            'transaction_context_equal':before['transaction']==after['transaction'],
            'window_start':before['captured_at'], 'window_end':after['captured_at'],
            'storage':'NOT VERIFIED in this DB-only run; private files were not accessed',
            'writer_attribution':'NOT VERIFIED; differences do not identify a writer'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--init-key', action='store_true')
    mode.add_argument('--snapshot', type=Path)
    mode.add_argument('--compare', type=Path)
    parser.add_argument('--after', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.init_key:
        write_private(args.key, os.urandom(32), binary=True)
        print('Private comparison key created')
        return 0
    key = read_private(args.key, binary=True)
    if len(key) != 32:
        raise ValueError('Invalid comparison key')
    from app.db.session import get_engine
    state = capture(get_engine(), key)
    if args.snapshot:
        write_private(args.snapshot, state)
        print('Read-only database snapshot created; no private files accessed')
        return 0
    if not args.after or not args.report:
        parser.error('Comparison requires exclusive --after and --report output paths')
    write_private(args.after, state)
    result = compare(read_private(args.compare), state)
    write_private(args.report, result)
    print(json.dumps(result, indent=2))
    return 0 if result['status']=='PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
