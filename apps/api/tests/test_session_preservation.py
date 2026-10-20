"""Privacy-preserving attribution limits and real authenticated-session updates."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import text
from test_auth import client, settings, payload, register, login
from session_preservation import compare, fingerprint, session_fingerprints, TABLES, write_private, read_private


def state(rows, key):
    return {'format_version':1,'key_id':'test-context','database_identity':'disposable',
            'captured_at':'synthetic window','transaction':{'transaction_read_only':'on'},
            'tables':{table:{'count':len(rows) if table=='auth_sessions' else 0,
                             'hash':fingerprint(key, table, rows if table=='auth_sessions' else [])} for table in TABLES},
            'revision':'synthetic revision','sessions':session_fingerprints(rows,key)}


def test_real_authenticated_get_changes_only_last_used_at(client, db, payload):
    register(client,payload)
    assert login(client,payload).status_code == 200
    rows = lambda: db.scalars(text('SELECT to_jsonb(t) FROM auth_sessions t ORDER BY id')).all()
    key = os.urandom(32)
    before = state(rows(), key)
    assert client.get('/api/v1/auth/me').status_code == 200
    result = compare(before, state(rows(),key))
    assert result['status'] == 'FAIL'  # Never ignore normal session activity to force PASS.
    assert result['changed_sessions'][0]['columns'] == ['last_used_at']
    assert result['changed_tables'] == {'auth_sessions':{'count_delta':0,'hash_changed':True}}
    assert result['sessions_added'] == result['sessions_removed'] == 0
    assert result['writer_attribution'].startswith('NOT VERIFIED')


def test_unauthenticated_get_does_not_touch_existing_session(client, db, payload):
    register(client,payload)
    assert login(client,payload).status_code == 200
    key = os.urandom(32)
    rows = lambda: db.scalars(text('SELECT to_jsonb(t) FROM auth_sessions t ORDER BY id')).all()
    before = state(rows(),key)
    client.cookies.clear()
    assert client.get('/api/v1/auth/me').status_code == 401
    assert compare(before,state(rows(),key))['status'] == 'PASS'


def test_column_changes_and_insert_delete_are_not_suppressed():
    key=os.urandom(32)
    old=[{'id':'synthetic-id','last_used_at':None,'revoked_at':None}]
    new=deepcopy(old);new[0]['revoked_at']='synthetic revocation'
    result=compare(state(old,key),state(new,key))
    assert result['status']=='FAIL' and result['changed_sessions'][0]['columns']==['revoked_at']
    result=compare(state(old,key),state([],key))
    assert result['status']=='FAIL' and result['sessions_removed']==1
    assert compare(state([],key),state(old,key))['sessions_added']==1


def test_fingerprints_do_not_disclose_values_or_reuse_keys():
    row={'id':'synthetic-identifier','token_hash':'synthetic credential representation'}
    key=os.urandom(32);serialized=json.dumps(session_fingerprints([row],key))
    assert all(value not in serialized for value in row.values())
    assert session_fingerprints([row],key)!=session_fingerprints([row],os.urandom(32))


def test_evidence_context_mismatch_is_refused():
    before=state([],os.urandom(32));after=deepcopy(before);after['database_identity']='different target'
    with pytest.raises(ValueError,match='Incompatible'):
        compare(before,after)


def test_private_evidence_is_exclusive_and_permissions_enforced(tmp_path):
    directory=tmp_path/'private';directory.mkdir(mode=0o700)
    path=directory/'snapshot.json'
    write_private(path,{'synthetic':'safe'})
    assert path.stat().st_mode & 0o777 == 0o600
    assert read_private(path)=={'synthetic':'safe'}
    with pytest.raises(FileExistsError):write_private(path,{'replace':True})
    path.chmod(0o644)
    with pytest.raises(ValueError,match='mode-0600'):read_private(path)
    path.chmod(0o600)
    link=directory/'symlink';link.symlink_to(path)
    with pytest.raises(OSError):read_private(link)
