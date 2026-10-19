"""Milestone 12 measurements for smoke.py's disposable HTTPS project only."""
import json
import os
from pathlib import Path
import platform
import subprocess
import threading
import time

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'infra/runtime/m12'


def database_sample(compose):
    query="""SELECT json_build_object('connections',(SELECT count(*) FROM pg_stat_activity),
    'max_connections',current_setting('max_connections'),
    'database_io',(SELECT row_to_json(s) FROM (SELECT blks_read,blks_hit,tup_returned,tup_fetched,temp_files,temp_bytes FROM pg_stat_database WHERE datname=current_database()) s),
    'pending_document_jobs',(SELECT count(*) FROM document_jobs WHERE state IN ('queued','running')),
    'pending_embedding_jobs',(SELECT count(*) FROM embedding_jobs WHERE state IN ('queued','running')),
    'failed_document_jobs',(SELECT count(*) FROM document_jobs WHERE state='failed'),
    'failed_embedding_jobs',(SELECT count(*) FROM embedding_jobs WHERE state='failed'))"""
    code="from app.container_entrypoint import configure; configure(); from app.db.session import get_engine; from sqlalchemy import text; import json; c=get_engine().connect(); print(json.dumps(c.scalar(text("+repr(query)+")))); c.close()"
    return json.loads(compose('exec','-T','api','python','-c',code,capture=True))


def load(directory,project,compose,fixture):
    OUT.mkdir(parents=True,exist_ok=True)
    target=directory/'load-fixture.json';target.write_text(json.dumps(fixture));target.chmod(0o600)
    ids=compose('ps','-q',capture=True).split()
    env=os.environ.copy();env['EVIDENCEAI_LOAD_FIXTURE']=str(target);env['EVIDENCEAI_LOAD_FINAL']=str(OUT/'load-final-stats.json')
    before=database_sample(compose)
    samples=[];stop=threading.Event()
    def sample():
        while not stop.is_set():
            result=subprocess.run(['docker','stats','--no-stream','--format','{{json .}}',*ids],text=True,capture_output=True)
            if result.returncode==0:
                samples.append({'elapsed_seconds':round(time.monotonic()-started,2),'containers':[json.loads(line) for line in result.stdout.splitlines() if line], 'database':database_sample(compose)})
            stop.wait(2)
    thresholds=json.loads((ROOT/'infra/load/thresholds.json').read_text())
    started=time.monotonic();thread=threading.Thread(target=sample,daemon=True);thread.start()
    try:
        with (OUT/'locust.log').open('w') as log:
            result=subprocess.run([os.environ.get('EVIDENCEAI_LOCUST','/tmp/evidenceai-m12-load/bin/locust'),
                '-f',str(ROOT/'infra/load/locustfile.py'),'--headless','--users',str(thresholds['users']),
                '--spawn-rate','1','--run-time',str(thresholds['duration_seconds'])+'s',
                '--csv',str(OUT/'load'),'--only-summary','--stop-timeout','10'],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=90)
    finally:
        stop.set();thread.join(timeout=8);target.unlink(missing_ok=True)
    elapsed=time.monotonic()-started
    after=database_sample(compose)
    rows=json.loads((OUT/'load-final-stats.json').read_text())
    aggregate=next(r for r in rows if r['Name']=='Aggregated')
    count=int(aggregate['Request Count']);failures=int(aggregate['Failure Count'])
    checks={'error_ratio':failures/max(count,1)<=thresholds['aggregate_error_ratio_max'],
        'p95':float(aggregate['95%'])<=thresholds['p95_ms_max'],
        'p99':float(aggregate['99%'])<=thresholds['p99_ms_max'],
        'sample_count':count>=thresholds['minimum_requests'],'runner_exit':result.returncode==0}
    deadline=time.monotonic()+thresholds['queue_drain_seconds_max'];drain_started=time.monotonic()
    while True:
        queue=database_sample(compose)
        if not queue['pending_document_jobs'] and not queue['pending_embedding_jobs']: break
        if time.monotonic()>deadline: break
        time.sleep(.5)
    checks['queue_drained']=not queue['pending_document_jobs'] and not queue['pending_embedding_jobs']
    checks['no_failed_jobs']=not queue['failed_document_jobs'] and not queue['failed_embedding_jobs']
    hardware=subprocess.check_output(['docker','info','--format','{{json .}}'],text=True)
    hardware=json.loads(hardware)
    report={'scope':'Disposable local TLS staging; synthetic tiny corpus, fake embeddings and mock LLM',
        'thresholds':thresholds,'checks':checks,'status':'PASS' if all(checks.values()) else 'FAIL',
        'elapsed_seconds':round(elapsed,3),'queue_drain_seconds':round(time.monotonic()-drain_started,3),
        'host':{'platform':platform.system(),'architecture':platform.machine(),'docker_cpus':hardware['NCPU'],'docker_memory_bytes':hardware['MemTotal']},
        'database_before':before,'database_after':after,'database_drained':queue,
        'stats':rows,'resource_samples':samples}
    (OUT/'load-result.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
