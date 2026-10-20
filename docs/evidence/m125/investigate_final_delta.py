import json,hashlib,itertools
from pathlib import Path
from sqlalchemy import text
from app.db.session import get_engine
before=json.loads(Path('/tmp/evidenceai-m125-before.json').read_text());report={'whole_development_database_equal':'FAIL','added_record_attribution':'NOT VERIFIED','scope':'Final12.5 observed delta; no rows deleted or reset'}
with get_engine().connect() as c:
 rows=c.scalars(text('select to_jsonb(t)::text from public.auth_rate_limits t order by key,window_start')).all();n=before['auth_rate_limits']['count']
 subsets=[subset for subset in itertools.combinations(range(len(rows)),n) if hashlib.sha256('\n'.join(rows[i] for i in subset).encode()).hexdigest()==before['auth_rate_limits']['hash']]
 report['original_limiter_rows_preserved']=bool(subsets);report['limiter_count_before']=n;report['limiter_count_after']=len(rows)
 if len(subsets)==1:
  extra=[json.loads(r) for i,r in enumerate(rows) if i not in subsets[0]]
  report['new_rows']=[{'window_start_utc':r['window_start'],'attempts':r['attempts'],'source_action_matches':[route for route in ['/api/v1/auth/register','/api/v1/auth/verify-registration','/api/v1/auth/login'] if hashlib.sha256((route+':127.0.0.1').encode()).hexdigest()==r['key']]} for r in extra]
 report['current_active_connections']=[{'application_name':r[0] or '(unset)','state':r[1],'count':r[2]} for r in c.execute(text("select application_name,state,count(*) from pg_stat_activity where datname=current_database() group by 1,2"))]
report['interpretation']='All preexisting limiter rows hash-match; an additional limiter record was observed late in the session. Loopback/action classification, if matched, does not identify an actor/process. No historical statement/connection audit is available. Owned test containers use separate databases and show zero public fixture rows, but these checks alone do not prove the writer of this development record.'
Path('docs/evidence/m125/database-final-delta.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
