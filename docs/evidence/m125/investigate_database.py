import hashlib,json,itertools
from pathlib import Path
from sqlalchemy import text
from app.db.session import get_engine
old=json.loads(Path('/tmp/evidenceai-m124-before.json').read_text());after=json.loads(Path('/tmp/evidenceai-m124-after.json').read_text())
report={'attribution':'NOT VERIFIED','method':'Read-only catalog/statistics and timestamps; values, email, key hashes and SQL text withheld','historical_before_counts':{t:old[t]['count'] for t in ['auth_rate_limits','registration_intents']},'historical_after_counts':{t:after[t]['count'] for t in ['auth_rate_limits','registration_intents']}}
with get_engine().connect() as c:
 report['database']=c.scalar(text('select current_database()'))
 report['schemas_with_target_tables']=[list(r) for r in c.execute(text("select table_schema,table_name from information_schema.tables where table_name in ('auth_rate_limits','registration_intents') order by 1,2"))]
 report['connection_summary']=[{'application':r[0] or '(unset)','state':r[1],'count':r[2]} for r in c.execute(text("select application_name,state,count(*) from pg_stat_activity where datname=current_database() group by 1,2 order by 1,2"))]
 report['logging_settings']={k:c.scalar(text('show '+k)) for k in ['log_statement','log_connections','log_disconnections','track_commit_timestamp']}
 intents=c.execute(text('select created_at,expires_at from public.registration_intents order by created_at')).all()
 report['registration_metadata']=[{'ordinal':i+1,'created_at_utc':r[0].isoformat(),'expires_at_utc':r[1].isoformat(),'ttl_seconds':(r[1]-r[0]).total_seconds()} for i,r in enumerate(intents)]
 report['limiter_windows']=[{'window_start_utc':r[0].isoformat(),'rows':r[1],'attempts_total':r[2]} for r in c.execute(text('select window_start,count(*),sum(attempts) from public.auth_rate_limits group by window_start order by window_start'))]
 for table,order in [('auth_rate_limits','key,window_start'),('registration_intents','id')]:
  rows=c.scalars(text(f'SELECT to_jsonb(t)::text FROM public.{table} t ORDER BY {order}')).all()
  report[table]={'current_count':len(rows),'matches_m124_after':hashlib.sha256('\n'.join(rows).encode()).hexdigest()==after[table]['hash']}
  if table=='auth_rate_limits':
   n=old[table]['count'];report['original_limiter_rows_preserved']=any(hashlib.sha256('\n'.join(subset).encode()).hexdigest()==old[table]['hash'] for subset in itertools.combinations(rows,n)) if len(rows)<30 else 'NOT VERIFIED; bounded subset search exceeded'
report['limitations']=['Limiter windows are time buckets, not creation timestamps.','No historical request/statement audit or actor ID captured by these tables; current pg_stat_activity cannot establish historical writers.','A registration intent proves persisted enrollment activity, not the originating process or person.','Timestamp coincidence or matching rate-limit hash cannot alone prove writer attribution.']
Path('docs/evidence/m125/database-investigation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
