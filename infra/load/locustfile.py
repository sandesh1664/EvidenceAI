"""Bounded synthetic HTTPS workload, launched only by the isolated staging drill.

No arbitrary target CLI: host must match the loopback private-CA fixture and the
fixture is created by smoke.py. Credentials never enter CSV or committed reports.
"""
import json
import os
from pathlib import Path
import uuid
from locust import HttpUser, between, task

fixture=json.loads(Path(os.environ['EVIDENCEAI_LOAD_FIXTURE']).read_text())
if fixture['origin']!='https://localhost:18443' or not fixture['project'].startswith('evidenceai-staging-smoke'):
    raise RuntimeError('Only the disposable staging fixture is permitted')


class Researcher(HttpUser):
    host=fixture['origin']
    wait_time=between(.5,1)

    def on_start(self):
        self.client.verify=fixture['ca']
        self.client.headers.update({'Origin':fixture['origin'],'X-CSRF-Protection':'1'})
        self.client.post('/api/v1/auth/login',json={'email':fixture['email'],'password':fixture['password']},name='authentication/login')

    @task(3)
    def auth(self): self.client.get('/api/v1/auth/me',name='authentication/me')

    @task(2)
    def workspaces(self):
        self.client.get('/api/v1/workspaces/',name='workspace/list')
        with self.client.post('/api/v1/workspaces/',json={'name':'Synthetic load '+uuid.uuid4().hex},name='workspace/create',catch_response=True) as response:
            if response.status_code!=201: return
            ident=response.json()['id']
        self.client.get('/api/v1/workspaces/'+ident,name='workspace/read')
        self.client.patch('/api/v1/workspaces/'+ident,json={'name':'Renamed load fixture'},name='workspace/update')
        self.client.delete('/api/v1/workspaces/'+ident,name='workspace/delete')

    @task(2)
    def search(self):
        self.client.post('/api/v1/workspaces/'+fixture['workspace']+'/search',json={'query':'solar panels convert'},name='vector/search')

    @task(1)
    def rag(self):
        self.client.post('/api/v1/workspaces/'+fixture['workspace']+'/ask',json={'question':'Solar panels convert','document_ids':[fixture['document']]},name='rag/mock-answer')

    @task(1)
    def upload(self):
        self.client.post('/api/v1/workspaces/'+fixture['workspace']+'/documents/',files={'file':('synthetic-load.txt',('Solar panels convert sunlight into renewable electricity. Fixture '+uuid.uuid4().hex).encode(),'text/plain')},name='document/upload')


# Locust's periodic CSV can lag the final requests. Preserve final in-memory
# counters at shutdown so acceptance does not silently use an earlier snapshot.
from locust import events


@events.quitting.add_listener
def save_final_stats(environment, **kwargs):
    def row(stats):
        value={'Type':stats.method or '', 'Name':stats.name,
            'Request Count':stats.num_requests,'Failure Count':stats.num_failures,
            'Min Response Time':stats.min_response_time,'Max Response Time':stats.max_response_time,
            'Average Response Time':stats.avg_response_time,'Requests/s':stats.total_rps}
        for percentile in (50,95,99):
            value[str(percentile)+'%']=stats.get_response_time_percentile(percentile/100)
        return value
    rows=[row(value) for value in environment.stats.entries.values()]+[row(environment.stats.total)]
    Path(os.environ['EVIDENCEAI_LOAD_FINAL']).write_text(json.dumps(rows,indent=2)+'\n')
