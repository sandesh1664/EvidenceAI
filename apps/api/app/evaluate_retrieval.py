"""Synthetic/offline retrieval benchmark; all data lives in a disposable schema."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import time
import uuid

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import get_engine
from app.db.disposable_database import require_disposable_database
from app.models import User, Workspace, WorkspaceMember, Document, DocumentChunk
from app.schemas.search import SearchRequest
from app.services import embedding_jobs, search_service
from app.services.embedding_providers import profile_for

DATASET = Path(__file__).resolve().parents[1]/'evaluation'/'retrieval.json'


def metrics(rankings,relevant,k):
    recalls,precisions,reciprocal,ndcgs = [],[],[],[]
    for ranking,truth in zip(rankings,relevant,strict=True):
        wanted=set(truth)
        hits=sum(item in wanted for item in ranking[:k])
        recalls.append(hits/len(wanted) if wanted else 0)
        precisions.append(hits/k)
        dcg=sum(1/math.log2(rank+1) for rank,item in enumerate(ranking[:k],1) if item in wanted)
        ideal=sum(1/math.log2(rank+1) for rank in range(1,min(k,len(wanted))+1))
        ndcgs.append(dcg/ideal if ideal else 0)
        reciprocal.append(next((1/rank for rank,item in enumerate(ranking[:k],1) if item in wanted),0))
    return {'recall_at_k':statistics.mean(recalls),'precision_at_k':statistics.mean(precisions),
            'mean_reciprocal_rank':statistics.mean(reciprocal),'ndcg_at_k':statistics.mean(ndcgs)}


def evaluate(dataset_path=DATASET, *, dimensions=128):
    require_disposable_database()
    dataset=json.loads(Path(dataset_path).read_text())
    settings=Settings(app_env='test',auth_allow_insecure_http=True,embedding_provider='fake',
        embedding_model='fake-hash-v1',embedding_revision='1',embedding_dimensions=dimensions,
        embedding_hosted_allowed=False,openai_api_key=None,trusted_frontend_origins=['http://localhost:3000'],
        search_min_similarity=0.25,embedding_batch_size=16,embedding_input_max_bytes=8000,
        embedding_http_timeout_seconds=10,embedding_request_budget_seconds=30,embedding_provider_attempts=3,
        embedding_job_max_attempts=3,embedding_job_lease_seconds=120)
    engine=get_engine()
    schema='eval_retrieval_'+uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    scratch=create_engine(get_settings().database_url.get_secret_value(),hide_parameters=True,
                         execution_options={'schema_translate_map':{None:schema}})
    try:
        Base.metadata.create_all(scratch)
        factory=sessionmaker(scratch,expire_on_commit=False)
        with factory() as db:
            owner=User(email=f'{uuid.uuid4()}@example.com',display_name='Synthetic evaluation owner')
            outsider=User(email=f'{uuid.uuid4()}@example.com',display_name='Synthetic outsider')
            db.add_all([owner,outsider]);db.flush()
            public=Workspace(name='Synthetic evaluation only',owner_id=owner.id)
            foreign=Workspace(name='Isolation distractors only',owner_id=outsider.id)
            db.add_all([public,foreign]);db.flush()
            db.add_all([WorkspaceMember(workspace_id=public.id,user_id=owner.id,role='owner'),
                        WorkspaceMember(workspace_id=foreign.id,user_id=outsider.id,role='owner')])
            mapping,foreign_ids={},set()
            for workspace,uploader in [(public,owner),(foreign,outsider)]:
                for record in dataset['documents']:
                    document=Document(workspace_id=workspace.id,uploaded_by=uploader.id,
                        original_filename=record['id']+'.txt',storage_key=uuid.uuid4().hex,
                        checksum_sha256=hashlib.sha256(record['text'].encode()).hexdigest(),
                        mime_type='text/plain',file_size=len(record['text'].encode()),processing_status='completed')
                    db.add(document);db.flush()
                    db.add(DocumentChunk(document_id=document.id,workspace_id=workspace.id,chunk_index=0,text=record['text'],
                        page_number=None,section='Synthetic',source_ref=f'document:{document.id}',char_start=0,char_end=len(record['text'])))
                    if workspace.id==public.id:mapping[document.id]=record['id']
                    else:foreign_ids.add(document.id)
                    db.flush()
                    embedding_jobs.enqueue(db,document,settings)
            db.commit()
            while embedding_jobs.run_once(db,settings):
                pass
            rankings,latencies,details=[],[],[]
            isolation_checks,isolation_passed=0,0
            for query in dataset['queries']:
                started=time.perf_counter()
                results=search_service.search(db,public.id,owner.id,SearchRequest(query=query['query'],limit=dataset['k']),settings)
                elapsed=(time.perf_counter()-started)*1000
                latencies.append(elapsed)
                assert all(result['document_id'] in mapping and result['document_id'] not in foreign_ids for result in results)
                isolation_checks+=1;isolation_passed+=1
                ranking=[mapping[result['document_id']] for result in results]
                rankings.append(ranking)
                details.append({'query_id':query['id'],'expected_document_ids':query['relevant'],'returned_document_ids':ranking,'latency_ms':round(elapsed,4)})
            for target,filters in [(foreign.id,None),(public.id,[next(iter(foreign_ids))])]:
                isolation_checks+=1
                try:
                    search_service.search(db,target,owner.id,SearchRequest(query='solar',document_ids=filters),settings)
                except HTTPException as error:
                    if error.status_code==404:isolation_passed+=1
            filter_checks=filter_passed=0
            for document_id in mapping:
                results=search_service.search(db,public.id,owner.id,SearchRequest(query=next(record['text'] for record in dataset['documents'] if record['id']==mapping[document_id]),document_ids=[document_id],limit=dataset['k']),settings)
                filter_checks+=1
                filter_passed+=bool(results) and all(result['document_id']==document_id for result in results)
            report={'document_filter_checks':filter_checks,'document_filter_passed':filter_passed,
                'document_filter_correctness':filter_passed/filter_checks,
                'empty_result_rate':sum(not ranking for ranking in rankings)/len(rankings),
                'embedding_dimensions':dimensions,'dataset' :dataset['name'],'provider':'fake','embedding_model':profile_for(settings).identifier,
                'quality_scope':'Synthetic lexical test-double evaluation; not hosted semantic-model accuracy',
                'k':dataset['k'],'workspace_documents':len(mapping),'foreign_workspace_documents':len(foreign_ids),
                'query_count':len(rankings),**metrics(rankings,[q['relevant'] for q in dataset['queries']],dataset['k']),
                'latency_mean_ms':round(statistics.mean(latencies),4),'latency_median_ms':round(statistics.median(latencies),4),
                'latency_p95_ms':round(sorted(latencies)[max(0,int(len(latencies)*0.95+0.999)-1)],4),
                'workspace_isolation_checks':isolation_checks,'workspace_isolation_passed':isolation_passed,
                'workspace_isolation_correctness':isolation_passed/isolation_checks,
                'created_at':datetime.now(timezone.utc).isoformat(),'queries':details}
            return report
    finally:
        scratch.dispose()
        assert schema.startswith('eval_retrieval_') and len(schema)==47
        with engine.begin() as connection:
            connection.execute(DropSchema(schema,cascade=True))


def main():
    parser=argparse.ArgumentParser(description='Evaluate synthetic retrieval in a disposable PostgreSQL schema')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    report=evaluate()
    serialized=json.dumps(report,indent=2)+'\n'
    if args.output:args.output.write_text(serialized)
    print(serialized,end='')


if __name__=='__main__':main()
