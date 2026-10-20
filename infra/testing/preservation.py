#!/usr/bin/env python3
"""Read-only development preservation snapshots; private paths stay outside Git.

Use the API virtualenv and PYTHONPATH=apps/api from the project root.
--snapshot writes mode0600 with O_EXCL; --compare never overwrites its input.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from sqlalchemy import text
from app.core.config import get_settings
from app.db.session import get_engine

TABLES=['users','workspaces','workspace_members','documents','auth_sessions','auth_rate_limits','document_chunks','document_jobs','storage_cleanup','embedding_profiles','chunk_embeddings','embedding_jobs','conversations','messages','message_citations','registration_intents']


def snapshot():
    state={}
    with get_engine().connect().execution_options(isolation_level='REPEATABLE READ') as c:
        c.execute(text('SET TRANSACTION READ ONLY'))
        for table in TABLES:
            order={'auth_rate_limits':'key,window_start','document_jobs':'document_id','storage_cleanup':'storage_key','chunk_embeddings':'chunk_id,profile_id','embedding_jobs':'document_id,profile_id'}.get(table,'id')
            rows=c.scalars(text(f'SELECT to_jsonb(t)::text FROM public.{table} t ORDER BY {order}')).all()
            state[table]={'count':len(rows),'hash':hashlib.sha256('\n'.join(rows).encode()).hexdigest()}
        state['revision']=c.scalar(text('SELECT version_num FROM public.alembic_version'))
    root=get_settings().document_storage_root;files={}
    if root.exists():
        for item in sorted([root,*root.rglob('*')]):
            stat=item.lstat();row={'mode':stat.st_mode,'uid':stat.st_uid,'gid':stat.st_gid,'mtime_ns':stat.st_mtime_ns}
            if item.is_symlink():row['link']=str(item.readlink())
            elif item.is_file():row.update(size=stat.st_size,sha256=hashlib.sha256(item.read_bytes()).hexdigest())
            files[str(item.relative_to(root))]=row
    state['storage']={'exists':root.exists(),'entries':files}
    return state


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--snapshot',type=Path);parser.add_argument('--compare',type=Path);parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    if bool(args.snapshot)==bool(args.compare):parser.error('Choose snapshot or compare')
    state=snapshot()
    if args.snapshot:
        with os.fdopen(os.open(args.snapshot,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:json.dump(state,f)
        print('Private snapshot written; no database writes');return 0
    before=json.loads(args.compare.read_text());equal=state==before
    result={'status':'PASS' if equal else 'FAIL','public_tables_compared':len(TABLES),'all_row_hashes_and_counts_equal':all(state[t]==before[t] for t in TABLES),'revision_equal':state['revision']==before['revision'],'private_storage_content_and_metadata_equal':state['storage']==before['storage'],'table_count_changes':{t:state[t]['count']-before[t]['count'] for t in TABLES if state[t]!=before[t]},'scope':'Current run only; does not resolve historical attribution or original evidence byte recovery.'}
    if args.report:args.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2));return 0 if equal else 1


if __name__=='__main__':raise SystemExit(main())
