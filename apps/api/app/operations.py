"""Authenticated diagnostics; bounded, read-only aggregation without customer fields."""
import argparse
import hmac
import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.telemetry import registry
from app.db.session import get_db, get_session_factory

REQUIRED_REVISION = '91e2b6d8c410'
router = APIRouter()


def authorize(request: Request):
    secret = get_settings().operations_token
    if not secret: raise HTTPException(404, 'Not found')
    supplied = request.headers.get('authorization', '')
    if not hmac.compare_digest(supplied.encode(), ('Bearer '+secret.get_secret_value()).encode()):
        raise HTTPException(401, 'Operator authorization required')


def queue_snapshot(db):
    """At most four state rows per table; server-side two-second statement budget.

    Own transaction only: callers must supply a fresh diagnostic session.
    """
    output = {}
    db.execute(text("SET LOCAL statement_timeout = '2000ms'"))
    db.execute(text("SET LOCAL lock_timeout = '500ms'"))
    db.execute(text('SET TRANSACTION READ ONLY'))
    for table in ('document_jobs', 'embedding_jobs'):
        rows = db.execute(text(f"""SELECT state, count(*) AS count,
            count(*) FILTER (WHERE state='running' AND lease_expires_at < clock_timestamp()) AS expired,
            coalesce(max(extract(epoch FROM clock_timestamp()-created_at)) FILTER (WHERE state='queued'),0) AS oldest_seconds
            FROM {table} GROUP BY state""")).mappings().all()
        output[table] = {state:{'count':0,'expired':0,'oldest_seconds':0.0} for state in ('queued','running','done','failed')}
        for row in rows:
            output[table][row['state']] = {'count':row['count'],'expired':row['expired'], 'oldest_seconds':max(0,float(row['oldest_seconds']))}
    output['cleanup'] = dict(db.execute(text('SELECT count(*) AS pending, coalesce(sum(attempts),0) AS retries FROM storage_cleanup')).mappings().one())
    output['cleanup']['retries'] = int(output['cleanup']['retries'])
    output['retries'] = {
        'document':int(db.scalar(text('SELECT coalesce(sum(greatest(processing_attempts-1,0)),0) FROM documents'))),
        'embedding':int(db.scalar(text('SELECT coalesce(sum(greatest(attempts-1,0)),0) FROM embedding_jobs')))}
    # Durable queue status is not a worker heartbeat or proof of process availability.
    output['worker_liveness'] = 'unverified'
    return output


def readiness(db, settings):
    checks = {'postgresql':False,'pgvector':False,'schema':False,'storage':False}
    try:
        db.execute(text("SET LOCAL statement_timeout = '2000ms'"))
        db.execute(text("SET LOCAL lock_timeout = '500ms'"))
        checks['postgresql'] = db.scalar(text('SELECT 1')) == 1
        checks['pgvector'] = bool(db.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')")))
        checks['schema'] = db.scalar(text('SELECT version_num FROM alembic_version')) == REQUIRED_REVISION
    except SQLAlchemyError:
        pass
    finally:
        db.rollback()
    root = Path(settings.document_storage_root)
    # Never create directories or read private files as part of a probe.
    try:
        checks['storage'] = root.is_dir() and root.resolve() == root and os.access(root, os.R_OK|os.W_OK|os.X_OK)
    except OSError:
        checks['storage'] = False
    providers = {'embedding':settings.embedding_provider, 'llm':settings.llm_provider}
    return {'ready':all(checks.values()),'checks':checks,'providers':providers}


@router.get('/api/v1/ready')
def ready(db=Depends(get_db)):
    result = readiness(db,get_settings())
    return JSONResponse({'status':'ready' if result['ready'] else 'not_ready'},status_code=200 if result['ready'] else 503)


@router.get('/api/v1/ops/readiness', dependencies=[Depends(authorize)])
def detailed_ready(db=Depends(get_db)):
    result = readiness(db,get_settings())
    try: result['queues'] = queue_snapshot(db)
    except SQLAlchemyError: result['queues'] = {'status':'unavailable'}
    finally: db.rollback()
    return JSONResponse(result,status_code=200 if result['ready'] else 503)


@router.get('/api/v1/ops/metrics', dependencies=[Depends(authorize)])
def metrics(db=Depends(get_db)):
    gauges = {
        'queue_jobs':'Retained durable jobs by queue and state.',
        'queue_expired':'Running jobs with expired leases.',
        'queue_oldest_seconds':'Oldest queued job age since creation in seconds.',
        'cleanup_pending':'Retained storage cleanup intents.',
        'job_retries':'Retries retained in current job and document rows.',
        'database_up':'Whether bounded diagnostic database aggregation succeeded.',
    }
    dynamic = [f'# HELP evidenceai_{name} {description}\n# TYPE evidenceai_{name} gauge\n' for name,description in gauges.items()]
    try:
        snapshot = queue_snapshot(db)
        for queue in ('document_jobs','embedding_jobs'):
            for state, values in snapshot[queue].items():
                for name in ('count','expired','oldest_seconds'):
                    dynamic.append(f'evidenceai_queue_{"jobs" if name == "count" else name}{{queue="{queue}",state="{state}"}} {values[name]}\n')
        dynamic.append(f'evidenceai_cleanup_pending {snapshot["cleanup"]["pending"]}\n')
        for kind, count in snapshot['retries'].items(): dynamic.append(f'evidenceai_job_retries{{kind="{kind}"}} {count}\n')
        dynamic.append('evidenceai_database_up 1\n')
    except SQLAlchemyError:
        dynamic.append('evidenceai_database_up 0\n')
    finally: db.rollback()
    return Response(registry.render()+''.join(dynamic),media_type='text/plain; version=0.0.4',headers={'Cache-Control':'no-store'})


def main():
    parser = argparse.ArgumentParser(description='Private local EvidenceAI queue/readiness diagnostics')
    parser.add_argument('--readiness',action='store_true')
    args = parser.parse_args()
    try:
        with get_session_factory()() as db:
            result = readiness(db,get_settings()) if args.readiness else queue_snapshot(db)
        print(json.dumps(result,indent=2))
        if args.readiness and not result['ready']: raise SystemExit(1)
    except SQLAlchemyError:
        print(json.dumps({'status':'unavailable','error_category':'database'}))
        raise SystemExit(1) from None


if __name__ == '__main__': main()
