import json,hashlib,xml.etree.ElementTree as ET
from datetime import datetime,timedelta,timezone
from pathlib import Path
from sqlalchemy import text
from app.db.session import get_engine
root=ET.parse('docs/evidence/m124/backend.xml').getroot().find('testsuite');start=datetime.fromisoformat(root.attrib['timestamp']);end=start+timedelta(seconds=float(root.attrib['time']))
report={'historical_pytest_interval_utc':{'start':start.astimezone(timezone.utc).isoformat(),'end':end.astimezone(timezone.utc).isoformat()},'hash_candidate_method':'Compare hashed limiter keys to source-defined auth route/action plus known loopback/TestClient labels, and recipient actions derived internally. No keys or recipients emitted.'}
with get_engine().connect() as c:
 intents=c.execute(text('select email,created_at from public.registration_intents')).all();report['intents_created_after_recorded_pytest_end']=sum(created>end for _,created in intents)
 keys=c.scalars(text("select key from public.auth_rate_limits where window_start >= '2026-10-19T21:20:00Z'" )).all()
 routes=['/api/v1/auth/register','/api/v1/auth/verify-registration','/api/v1/auth/login','/api/v1/auth/logout']
 report['new_limiter_client_matches']={label:sum(k in {hashlib.sha256((route+':'+label).encode()).hexdigest() for route in routes} for k in keys) for label in ['127.0.0.1','::1','testclient','unknown']}
 expected={hashlib.sha256(('registration-email:registration-email:'+email).encode()).hexdigest() for email,_ in intents};report['new_limiter_matching_existing_intent_recipient_actions']=sum(k in expected for k in keys)
report['interpretation']='The recorded pytest invocation ended before these intents were created; no attribution to a different process, browser fixture, API caller or actor follows from timing or hash matches alone. Historical statement/access logs are unavailable.'
Path('docs/evidence/m125/database-correlation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
