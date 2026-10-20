"""Independent connections exercise real PostgreSQL locks through authenticated HTTP.

Only a uniquely named scratch schema is created/removed. Public application tables
and all pre-existing data are untouched. Ordinary API tests use rollback fixtures.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event, Lock
import time
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.security import hash_token, new_session_token
from app.db.base import Base
from app.db.session import get_db, get_engine
from app.main import app
from app.models import User, Workspace, WorkspaceMember, AuthSession
from app.schemas.workspace import WorkspaceCreate
from app.schemas.workspace_member import MemberCreate
from app.services import workspace_service as workspaces, workspace_member_service as members

ORIGIN = 'http://localhost:3000'


@pytest.fixture
def scratch_database():
    # This identifier is generated here, never accepted from configuration or input.
    schema = 'test_workspace_' + uuid.uuid4().hex
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    scratch = create_engine(get_settings().database_url.get_secret_value(), hide_parameters=True,
                            execution_options={'schema_translate_map': {None: schema}},
                            connect_args={'options': f'-c search_path={schema},public -c statement_timeout=15000 -c lock_timeout=5000'})
    try:
        Base.metadata.create_all(scratch)
        yield scratch
    finally:
        scratch.dispose()
        assert schema.startswith('test_workspace_') and len(schema) == 47
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))


@pytest.fixture
def concurrent_api(scratch_database, monkeypatch):
    factory = sessionmaker(scratch_database, expire_on_commit=False)
    with factory() as db:
        people, tokens = {}, {}
        for role in ['owner','admin','member','candidate']:
            user = User(email=f'{uuid.uuid4()}@example.com', display_name=role,
                        password_hash='not-a-login-hash-for-session-only-test')
            db.add(user)
            db.flush()
            people[role] = user.id
            tokens[role] = new_session_token()
            db.add(AuthSession(user_id=user.id, token_hash=hash_token(tokens[role]),
                               expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
        db.commit()
        workspace = workspaces.create_workspace(db,people['owner'],WorkspaceCreate(name='Concurrent'))
        workspace_id = workspace.id
        for role in ['admin','member']:
            members.add_member(db,workspace_id,people['owner'],MemberCreate(user_id=people[role],role=role))

    settings = Settings(app_env='test', auth_allow_insecure_http=True, trusted_frontend_origins=[ORIGIN])
    import app.core.browser_security as browser
    monkeypatch.setattr(browser,'get_settings',lambda:settings)
    def isolated_db():
        with factory() as db:
            try:
                yield db
            except Exception:
                db.rollback()
                raise
    app.dependency_overrides[get_db] = isolated_db
    app.dependency_overrides[get_settings] = lambda:settings
    app.middleware_stack = None
    def request(role, method, suffix, body):
        with TestClient(app, headers={'Origin':ORIGIN, 'X-CSRF-Protection':'1'}) as client:
            client.cookies.set('evidenceai_session',tokens[role])
            return client.request(method,f'/api/v1/workspaces/{workspace_id}'+suffix,json=body)
    try:
        yield scratch_database, factory, people, workspace_id, request
    finally:
        app.dependency_overrides.clear()
        app.middleware_stack = None


@pytest.mark.parametrize('scenario,expected', [
    ('competing_transfers',[200,403]),
    ('transfer_then_remove_new_owner',[200,409]),
    ('remove_then_transfer_to_member',[204,404]),
    ('duplicate_member_addition',[201,409]),
    ('demote_then_admin_update',[200,403]),
    ('remove_admin_then_admin_add',[204,404]),
])
def test_concurrent_mutations_reauthorize_after_lock(concurrent_api,monkeypatch,scenario,expected):
    engine, factory, people, workspace_id, request = concurrent_api
    original = members.workspace_access
    first_locked, second_started, release_first = Event(), Event(), Event()
    mutex, pids, references = Lock(), [], []

    def gated_access(db, workspace_id, actor_id, *, lock=False):
        assert lock
        pid = db.scalar(select(func.pg_backend_pid()))
        # Hold stale objects in the second Session identity map BEFORE waiting.
        # The implementation must refresh both workspace and membership after locking.
        cached_workspace = db.get(Workspace,workspace_id)
        cached_member = db.scalar(select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == actor_id))
        with mutex:
            index = len(pids)
            pids.append(pid)
            references.append((cached_workspace,cached_member))
        if index == 0:
            result = original(db,workspace_id,actor_id,lock=True)
            first_locked.set()
            if not release_first.wait(8):
                raise RuntimeError('Test did not release first workspace lock')
            return result
        second_started.set()
        return original(db,workspace_id,actor_id,lock=True)

    monkeypatch.setattr(members,'workspace_access',gated_access)
    monkeypatch.setattr(workspaces,'workspace_access',gated_access)
    transfer_member = ('owner','POST','/transfer-ownership',{'new_owner_id':str(people['member'])})
    remove_member = ('owner','DELETE',f'/members/{people["member"]}',None)
    add_candidate = ('owner','POST','/members',{'user_id':str(people['candidate'])})
    if scenario == 'competing_transfers':
        first = transfer_member
        second = ('owner','POST','/transfer-ownership',{'new_owner_id':str(people['admin'])})
    elif scenario == 'transfer_then_remove_new_owner': first,second = transfer_member,remove_member
    elif scenario == 'remove_then_transfer_to_member': first,second = remove_member,transfer_member
    elif scenario == 'duplicate_member_addition': first,second = add_candidate,add_candidate
    elif scenario == 'demote_then_admin_update':
        first = ('owner','PATCH',f'/members/{people["admin"]}',{'role':'member'})
        second = ('admin','PATCH','',{'name':'Unauthorized stale admin update'})
    else:
        first = ('owner','DELETE',f'/members/{people["admin"]}',None)
        second = ('admin','POST','/members',{'user_id':str(people['candidate'])})

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(request,*first)
        second_future = None
        try:
            assert first_locked.wait(5), 'First request failed to lock the workspace'
            second_future = pool.submit(request,*second)
            assert second_started.wait(5), 'Second request did not reach authorization'
            # Prove actual DB lock contention, rather than merely starting two threads.
            deadline, blocked = time.monotonic()+5, False
            with engine.connect() as observer:
                while time.monotonic() < deadline:
                    blockers = observer.scalar(select(func.pg_blocking_pids(pids[1])))
                    if pids[0] in blockers:
                        blocked = True
                        break
                    time.sleep(0.01)
            assert blocked, 'Second PostgreSQL transaction did not wait for the first lock'
        finally:
            release_first.set()
        assert second_future is not None
        responses = [first_future.result(timeout=5),second_future.result(timeout=5)]
    assert [response.status_code for response in responses] == expected, [r.text for r in responses]
    with factory() as db:
        workspace = db.get(Workspace,workspace_id)
        owners = db.scalars(select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,WorkspaceMember.role == 'owner')).all()
        new_owner = people['member'] if scenario in {'competing_transfers','transfer_then_remove_new_owner'} else people['owner']
        assert workspace.owner_id == new_owner
        assert len(owners) == 1 and owners[0].user_id == new_owner
        if scenario == 'duplicate_member_addition':
            assert len(db.scalars(select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,WorkspaceMember.user_id == people['candidate'])).all()) == 1
        assert workspace.name == 'Concurrent'
