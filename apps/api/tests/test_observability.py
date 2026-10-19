import asyncio
import json
import logging
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.exc import OperationalError

from app.core.telemetry import Registry, SafeJSONFormatter, RequestTelemetryMiddleware, category, measured, registry, request_id, valid_id
from app import operations
from app.evaluate import check_thresholds, latency_summary, save_report
from app.evaluate_retrieval import metrics
from app.document_worker import write_metrics


def test_content_free_logging():
    record=logging.LogRecord('private',logging.ERROR,'private/path',1,'password=%s',('secret-token',),None)
    record.safe={'operation':'retrieval','request_id':str(uuid4()),'workspace_id':str(uuid4()),
        'password':'secret-key','route':'/api/v1/workspaces/{workspace_id}/search', 'duration_ms':12,
        'provider':'secretkey','question':'private question'}
    output=SafeJSONFormatter().format(record)
    data=json.loads(output)
    assert data['operation']=='retrieval' and data['severity']=='ERROR'
    assert not any(value in output for value in ('secret','password','private','question'))
    assert set(data)=={'timestamp','severity','operation','request_id','workspace_id','route','duration_ms'}


@pytest.mark.parametrize('value',['arbitrary','a'*10000,'\r\nsecret',str(uuid4()).upper(),None])
def test_invalid_identifiers(value): assert not valid_id(value)


def test_http_correlation_and_database_failure():
    app=FastAPI();app.add_middleware(RequestTelemetryMiddleware)
    @app.get('/test/{identifier}')
    def endpoint(identifier: str): return {'id':request_id.get()}
    @app.get('/database-failure')
    def broken(): raise OperationalError('secret SQL',{'key':'secret'},Exception('private database URL'))
    with TestClient(app) as client:
        identifier=str(uuid4())
        response=client.get('/test/private-document?question=secret',headers={'X-Request-ID':identifier})
        assert response.json()['id']==identifier==response.headers['x-request-id']
        generated=client.get('/test/a',headers={'X-Request-ID':'unsafe-value'})
        assert valid_id(generated.headers['x-request-id'])
        failure=client.get('/database-failure')
        assert failure.status_code==503
        assert failure.json()=={'detail':'Service temporarily unavailable','request_id':failure.headers['x-request-id']}
        assert 'secret' not in failure.text and 'private' not in failure.text
    assert request_id.get() is None
    rendered=registry.render()
    assert 'route="/test/{identifier}"' in rendered
    assert 'private-document' not in rendered and 'question=' not in rendered


def test_registry_counts_and_histogram():
    local=Registry();local.count('example_total',amount=2)
    local.observe('example_seconds',(),.02);local.observe('example_seconds',(),.2)
    output=local.render()
    assert 'evidenceai_example_total 2.0' in output
    assert 'evidenceai_example_seconds_count 2' in output
    assert 'evidenceai_example_seconds_bucket{le="0.025"} 1' in output
    assert 'evidenceai_example_seconds_bucket{le="+Inf"} 2' in output


def test_provider_failure_metrics():
    from types import SimpleNamespace
    class Provider:
        settings=SimpleNamespace(llm_provider='mock')
        @measured('generation',provider=True)
        def generate(self): raise TimeoutError('secret input')
    with pytest.raises(TimeoutError): Provider().generate()
    assert 'operation="generation",outcome="failure",provider="mock"' in registry.render()


def test_cancellation_propagates():
    async def fail(scope,receive,send): raise asyncio.CancelledError()
    async def run():
        with pytest.raises(asyncio.CancelledError):
            await RequestTelemetryMiddleware(fail)({'type':'http','headers':[],'method':'GET'},None,None)
    asyncio.run(run())
    assert request_id.get() is None and category(asyncio.CancelledError())=='cancelled'


def test_operator_access(monkeypatch,tmp_path):
    from app.core.config import Settings
    settings=Settings(document_storage_root=tmp_path)
    monkeypatch.setattr(operations,'get_settings',lambda:settings)
    app=FastAPI();app.include_router(operations.router)
    with TestClient(app) as client:
        assert client.get('/api/v1/ops/metrics').status_code==404
        settings.operations_token=SecretStr('x'*40)
        assert client.get('/api/v1/ops/metrics').status_code==401
        assert client.get('/api/v1/ops/readiness',headers={'Authorization':'Bearer wrong'}).status_code==401
        assert client.get('/api/v1/ops/metrics',headers={'Cookie':'evidenceai_session=private'}).status_code==401


def test_readiness_and_queue_real_database(tmp_path):
    from app.core.config import Settings
    from app.db.session import get_session_factory
    settings=Settings(document_storage_root=tmp_path,embedding_provider='disabled',llm_provider='disabled')
    with get_session_factory()() as db:
        result=operations.readiness(db,settings)
        assert result['ready'] and all(result['checks'].values())
        assert result['providers']=={'embedding':'disabled','llm':'disabled'}
        snapshot=operations.queue_snapshot(db)
        assert snapshot['worker_liveness']=='unverified'
        assert set(snapshot['document_jobs'])=={'queued','running','done','failed'}
        assert not any(word in json.dumps(snapshot) for word in ('email','filename','storage_key','workspace_id','user_id'))


def test_database_down_readiness(tmp_path):
    from app.core.config import Settings
    class Broken:
        def execute(self,*_): raise OperationalError('secret',{},Exception('password'))
        def rollback(self): pass
    result=operations.readiness(Broken(),Settings(document_storage_root=tmp_path))
    assert not result['ready'] and not result['checks']['postgresql']
    assert 'secret' not in json.dumps(result)


def test_atomic_worker_metrics(tmp_path):
    path=tmp_path/'worker.prom';write_metrics(path);write_metrics(path)
    assert 'evidenceai_worker_last_tick_timestamp_seconds ' in path.read_text()
    assert list(tmp_path.iterdir())==[path]
    assert path.stat().st_mode & 0o777 == 0o640


def test_ndcg_and_thresholds():
    report=metrics([['wrong','relevant']],[['relevant']],2)
    assert report['recall_at_k']==1 and report['precision_at_k']==.5
    assert report['mean_reciprocal_rank']==.5
    assert report['ndcg_at_k']==pytest.approx(1/1.584962500721156)
    assert not check_thresholds({'x':1},{'x':{'min':1}})
    assert check_thresholds({'x':.5},{'x':{'min':1,'max_drop':.1}},{'x':1})
    assert check_thresholds({}, {'x':{'min':1}})
    assert check_thresholds({'x':float('nan')},{'x':{'min':1}})


def test_sample_gated_percentiles_and_history(tmp_path):
    assert latency_summary([])['p50_ms'] is None
    assert latency_summary(range(19))['p95_ms'] is None
    assert latency_summary(range(20))['p95_ms']==18
    assert latency_summary(range(99))['p99_ms'] is None
    assert latency_summary(range(100))['p99_ms']==98
    a=save_report({'synthetic':True},tmp_path);b=save_report({'synthetic':False},tmp_path)
    assert a!=b and json.loads(a.read_text())=={'synthetic':True}


def test_extended_rag_evaluation():
    from app.evaluate_rag import evaluate
    report=evaluate(extended=True);cases={case['id']:case for case in report['cases']}
    assert report['case_count']==18
    for name in ('provider-outage','provider-timeout','retrieval-outage','unsupported-numerical-claim'):
        assert cases[name]['correct'], cases[name]
    assert all(guard['correct'] for guard in report['guards'])
    assert report['citation_reference_validity']==1 and report['insufficient_evidence_recall']==1


def test_authorized_metrics_and_readiness(monkeypatch,tmp_path):
    from app.core.config import Settings
    from app.db.session import get_db, get_session_factory
    settings=Settings(document_storage_root=tmp_path,operations_token='x'*40)
    monkeypatch.setattr(operations,'get_settings',lambda:settings)
    app=FastAPI();app.include_router(operations.router)
    def database():
        with get_session_factory()() as db: yield db
    app.dependency_overrides[get_db]=database
    with TestClient(app) as client:
        headers={'Authorization':'Bearer '+'x'*40}
        response=client.get('/api/v1/ops/metrics',headers=headers)
        assert response.status_code==200 and 'evidenceai_database_up 1' in response.text
        assert 'evidenceai_queue_jobs{queue="document_jobs",state="queued"}' in response.text
        assert 'text/plain' in response.headers['content-type']
        assert not any(word in response.text for word in ('password','storage_key','workspace_id=','question='))
        assert client.get('/api/v1/ready').json()=={'status':'ready'}
        detailed=client.get('/api/v1/ops/readiness',headers=headers)
        assert detailed.status_code==200 and detailed.json()['queues']['worker_liveness']=='unverified'
        Path('/tmp/evidenceai-m10-metrics.prom').write_text(response.text)


def test_worker_graceful_signal(tmp_path):
    import subprocess
    import sys
    import time
    # Exercise the real CLI loop/signal handler with in-memory stubs, no public work.
    script = '''
import sys
from contextlib import nullcontext
from types import SimpleNamespace
from pathlib import Path
from app import document_worker as worker
worker.get_settings=lambda: SimpleNamespace()
worker.get_session_factory=lambda: lambda: nullcontext(None)
worker.get_document_storage=lambda: None
worker.run_once=lambda *args: False
worker.main()
'''
    path=tmp_path/'worker.prom'
    process=subprocess.Popen([sys.executable,'-c',script,'--metrics-file',str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        deadline=time.monotonic()+5
        while not path.exists() and time.monotonic()<deadline:
            if process.poll() is not None: break
            time.sleep(.02)
        assert path.exists()
        process.terminate()
        stdout,stderr=process.communicate(timeout=5)
        assert process.returncode==0 and b'worker_stopped' in stderr
    finally:
        if process.poll() is None: process.kill();process.wait()


def test_metrics_database_failure_is_safe(monkeypatch):
    class Broken:
        def execute(self,*_): raise OperationalError('secret',{},Exception('private credentials'))
        def rollback(self): pass
    response=operations.metrics(Broken())
    assert 'evidenceai_database_up 0' in response.body.decode()
    assert 'secret' not in response.body.decode() and 'credentials' not in response.body.decode()


from test_workspace_concurrency import scratch_database


def test_queue_aggregates_expiration_retries_and_age(scratch_database):
    from datetime import timedelta
    from sqlalchemy import select, func, text
    from sqlalchemy.orm import sessionmaker
    from app.models import User, Workspace, Document, DocumentJob, StorageCleanup
    schema=scratch_database.get_execution_options()['schema_translate_map'][None]
    with sessionmaker(scratch_database,expire_on_commit=False)() as db:
        user=User(email=f'{uuid4()}@example.com',display_name='Synthetic')
        db.add(user);db.flush()
        workspace=Workspace(name='Synthetic queue',owner_id=user.id)
        db.add(workspace);db.flush()
        now=db.scalar(select(func.clock_timestamp()))
        for i,state in enumerate(('queued','running','done','failed')):
            document=Document(workspace_id=workspace.id,uploaded_by=user.id,original_filename='not logged.txt',
                storage_key=uuid4().hex,checksum_sha256=str(i)*64,processing_attempts=3)
            db.add(document);db.flush()
            db.add(DocumentJob(document_id=document.id,state=state,created_at=now-timedelta(seconds=120),
                lease_id=uuid4() if state=='running' else None,
                lease_expires_at=now-timedelta(seconds=1) if state=='running' else None))
        db.add(StorageCleanup(storage_key=uuid4().hex,attempts=2));db.commit()
        # Raw operator SQL intentionally uses the connection's normal schema search path.
        db.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
        result=operations.queue_snapshot(db)
        assert all(value['count']==1 for value in result['document_jobs'].values())
        assert result['document_jobs']['running']['expired']==1
        assert result['document_jobs']['queued']['oldest_seconds']>=120
        assert result['cleanup']=={'pending':1,'retries':2}
        assert result['retries']['document']==8



def test_worker_metrics_failure_does_not_stop_tick(monkeypatch,tmp_path):
    from contextlib import nullcontext
    import sys
    from app import document_worker as worker
    monkeypatch.setattr(worker,'get_settings',lambda:None)
    monkeypatch.setattr(worker,'get_session_factory',lambda:lambda:nullcontext(None))
    monkeypatch.setattr(worker,'get_document_storage',lambda:None)
    monkeypatch.setattr(worker,'run_once',lambda *_:False)
    monkeypatch.setattr(worker.signal,'signal',lambda *_:None)
    monkeypatch.setattr(worker,'configure_logging',lambda:None)
    def failed(*_): raise OSError('PRIVATE storage failure')
    monkeypatch.setattr(worker,'write_metrics',failed)
    monkeypatch.setattr(sys,'argv',['worker','--once','--metrics-file',str(tmp_path/'worker.prom')])
    worker.main()
