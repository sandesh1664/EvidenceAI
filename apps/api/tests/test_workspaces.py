"""Workspace API tests use real sessions and the existing PostgreSQL rollback fixtures."""
from datetime import datetime, timedelta, timezone
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event, select, func
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.core.config import Settings, get_settings
from app.core.security import hash_token, new_session_token, password_hasher
from app.db.session import get_db
from app.models import User, Workspace, WorkspaceMember, Document, AuthSession
from app.schemas.workspace import WorkspaceCreate
from app.schemas.workspace_member import MemberCreate
from app.services import workspace_service as workspaces, workspace_member_service as members

ORIGIN = 'http://localhost:3000'
HEADERS = {'Origin': ORIGIN, 'X-CSRF-Protection': '1'}
BASE = '/api/v1/workspaces'


@pytest.fixture(scope='module')
def encoded_password():
    return password_hasher.hash('a secure test password!')


@pytest.fixture
def people(db, encoded_password):
    users = {}
    for role in ['owner', 'admin', 'member', 'outsider', 'candidate']:
        user = User(email=f'{uuid.uuid4()}@example.com', display_name=role, password_hash=encoded_password)
        db.add(user)
        db.flush()
        token = new_session_token()
        db.add(AuthSession(user_id=user.id, token_hash=hash_token(token),
                           expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        users[role] = (user, token)
    db.commit()
    return users


def identity(people, role):
    return people[role][0].id


def sign_in(client, people, role):
    client.cookies.clear()
    client.cookies.set('evidenceai_session', people[role][1])


@pytest.fixture
def client(db, people, monkeypatch):
    settings = Settings(app_env='test', auth_allow_insecure_http=True,
                        trusted_frontend_origins=[ORIGIN], auth_rate_limit=100)
    import app.core.browser_security as browser
    monkeypatch.setattr(browser, 'get_settings', lambda: settings)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_settings] = lambda: settings
    app.middleware_stack = None
    try:
        with TestClient(app, headers=HEADERS) as client:
            sign_in(client, people, 'owner')
            yield client
    finally:
        app.dependency_overrides.clear()
        app.middleware_stack = None


@pytest.fixture
def workspace(db, people):
    workspace = workspaces.create_workspace(db, identity(people, 'owner'), WorkspaceCreate(name='Research'))
    for role in ['admin', 'member']:
        members.add_member(db, workspace.id, identity(people, 'owner'),
                           MemberCreate(user_id=identity(people, role), role=role))
    return workspace


def endpoint(workspace):
    return f'{BASE}/{workspace.id}'


def assert_owner_invariant(db, workspace_id, owner_id):
    db.expire_all()
    workspace = db.get(Workspace, workspace_id)
    owners = db.scalars(select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.role == 'owner')).all()
    assert workspace.owner_id == owner_id
    assert len(owners) == 1 and owners[0].user_id == owner_id


def test_create_and_atomic_owner_membership(client, db, people):
    response = client.post(BASE+'/', json={'name':'  New workspace  ', 'description':'Private research'})
    assert response.status_code == 201, response.text
    result = response.json()
    assert set(result) == {'id','name','description','owner_id','created_at','updated_at'}
    assert result['name'] == 'New workspace' and result['description'] == 'Private research'
    assert result['owner_id'] == str(identity(people, 'owner'))
    assert_owner_invariant(db, uuid.UUID(result['id']), identity(people, 'owner'))
    assert len(db.scalars(select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == uuid.UUID(result['id']))).all()) == 1


@pytest.mark.parametrize('payload', [
    {}, {'name':' '}, {'name':'x'*201}, {'name':None}, {'name':'X','description':'x'*10001},
    {'name':'X','owner_id':str(uuid.uuid4())}, {'name':'X','role':'owner'},
])
def test_invalid_create_payload(client, payload):
    assert client.post(BASE+'/', json=payload).status_code == 422


def test_lists_only_accessible_workspaces(client, db, people, workspace):
    other = workspaces.create_workspace(db, identity(people, 'outsider'), WorkspaceCreate(name='Hidden'))
    for role in ['owner','admin','member']:
        sign_in(client, people, role)
        results = client.get(BASE+'/').json()
        assert [item['id'] for item in results] == [str(workspace.id)]
    sign_in(client, people, 'outsider')
    assert [item['id'] for item in client.get(BASE+'/').json()] == [str(other.id)]
    sign_in(client, people, 'candidate')
    assert client.get(BASE+'/').json() == []


@pytest.mark.parametrize('method,path,payload', [
    ('POST', '/', {'name':'X'}), ('GET','/',None),
    ('GET','/{workspace}',None), ('PATCH','/{workspace}',{'name':'X'}), ('DELETE','/{workspace}',None),
    ('GET','/{workspace}/members',None), ('POST','/{workspace}/members',{'user_id':'{user}'}),
    ('PATCH','/{workspace}/members/{user}',{'role':'admin'}), ('DELETE','/{workspace}/members/{user}',None),
    ('POST','/{workspace}/transfer-ownership',{'new_owner_id':'{user}'}),
])
def test_all_endpoints_require_authentication(client, workspace, people, method, path, payload):
    client.cookies.clear()
    path = path.format(workspace=workspace.id, user=identity(people,'member'))
    if payload:
        payload = {k:v.format(user=identity(people,'member')) for k,v in payload.items()}
    assert client.request(method, BASE+path, json=payload).status_code == 401


@pytest.mark.parametrize('method,suffix,payload', [
    ('GET','',None), ('PATCH','',{'name':'Stolen'}), ('DELETE','',None),
    ('GET','/members',None), ('POST','/members',{'user_id':'{user}'}),
    ('PATCH','/members/{user}',{'role':'admin'}), ('DELETE','/members/{user}',None),
    ('POST','/transfer-ownership',{'new_owner_id':'{user}'}),
])
def test_cross_workspace_isolation_and_missing_indistinguishable(client, people, workspace, method, suffix, payload):
    sign_in(client, people, 'outsider')
    suffix = suffix.format(user=identity(people,'member'))
    if payload:
        payload = {k:v.format(user=identity(people,'member')) for k,v in payload.items()}
    hidden = client.request(method, endpoint(workspace)+suffix, json=payload)
    missing = client.request(method, f'{BASE}/{uuid.uuid4()}'+suffix, json=payload)
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json() == {'detail':'Workspace not found'}


@pytest.mark.parametrize('role', ['owner','admin','member'])
def test_workspace_and_members_readable(client, people, workspace, role):
    sign_in(client, people, role)
    assert client.get(endpoint(workspace)).status_code == 200
    response = client.get(endpoint(workspace)+'/members')
    assert response.status_code == 200 and len(response.json()) == 3
    assert {item['role'] for item in response.json()} == {'owner','admin','member'}
    for item in response.json():
        assert set(item) == {'id','workspace_id','user_id','role','joined_at'}
    assert 'email' not in response.text and 'password' not in response.text


@pytest.mark.parametrize('role,status', [('owner',200),('admin',200),('member',403)])
def test_update_workspace_permissions(client, people, workspace, role, status):
    sign_in(client, people, role)
    response = client.patch(endpoint(workspace), json={'name':'Updated', 'description':'New details'})
    assert response.status_code == status
    if status == 200: assert response.json()['name'] == 'Updated'
    else: assert client.get(endpoint(workspace)).json()['name'] == 'Research'


def test_patch_omitted_and_null_description(client, workspace):
    assert client.patch(endpoint(workspace), json={'description':'Details'}).status_code == 200
    response = client.patch(endpoint(workspace), json={'name':'Changed'})
    assert response.json()['description'] == 'Details'
    response = client.patch(endpoint(workspace), json={'description':None})
    assert response.json()['description'] is None and response.json()['name'] == 'Changed'


@pytest.mark.parametrize('payload', [{}, {'name':None}, {'name':' '}, {'name':'x'*201},
    {'description':'x'*10001}, {'owner_id':str(uuid.uuid4())}, {'role':'owner'}])
def test_invalid_update(client, workspace, payload):
    assert client.patch(endpoint(workspace), json=payload).status_code == 422


@pytest.mark.parametrize('role,status', [('owner',201),('admin',201),('member',403)])
@pytest.mark.parametrize('assigned_role', ['member','admin'])
def test_add_member_permissions(client, people, workspace, role, status, assigned_role):
    sign_in(client, people, role)
    response = client.post(endpoint(workspace)+'/members',
                           json={'user_id':str(identity(people,'candidate')), 'role':assigned_role})
    assert response.status_code == status
    if status == 201:
        assert response.json()['role'] == assigned_role
        assert response.json()['user_id'] == str(identity(people,'candidate'))


def test_default_member_role(client, people, workspace):
    response = client.post(endpoint(workspace)+'/members', json={'user_id':str(identity(people,'candidate'))})
    assert response.status_code == 201 and response.json()['role'] == 'member'


def test_duplicate_membership_and_rollback(client, db, people, workspace):
    response = client.post(endpoint(workspace)+'/members', json={'user_id':str(identity(people,'member'))})
    assert response.status_code == 409
    assert len(db.scalars(select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace.id)).all()) == 3
    assert client.patch(endpoint(workspace),json={'name':'Still usable'}).status_code == 200


@pytest.mark.parametrize('kind', ['missing','inactive','unregistered'])
def test_eligible_user_errors_are_generic(client, db, people, workspace, kind):
    user_id = identity(people,'candidate')
    if kind == 'missing': user_id = uuid.uuid4()
    elif kind == 'inactive': people['candidate'][0].is_active = False
    else: people['candidate'][0].password_hash = None
    db.commit()
    response = client.post(endpoint(workspace)+'/members', json={'user_id':str(user_id)})
    assert response.status_code == 404 and response.json() == {'detail':'Eligible user not found'}
    assert 'email' not in response.text and 'inactive' not in response.text


@pytest.mark.parametrize('role,status', [('owner',200),('admin',200),('member',403)])
def test_change_ordinary_member_role(client, people, workspace, role, status):
    sign_in(client, people, role)
    response = client.patch(endpoint(workspace)+f'/members/{identity(people,"member")}', json={'role':'admin'})
    assert response.status_code == status
    if status == 200: assert response.json()['role'] == 'admin'


@pytest.mark.parametrize('role', ['owner','admin','member'])
@pytest.mark.parametrize('method', ['POST','PATCH'])
def test_owner_role_cannot_be_assigned_in_membership_payload(client, db, people, workspace, role, method):
    sign_in(client, people, role)
    path = endpoint(workspace)+'/members'
    data = {'role':'owner'}
    if method == 'POST': data['user_id'] = str(identity(people,'candidate'))
    else: path += f'/{identity(people,role)}'
    assert client.request(method,path,json=data).status_code == 422
    assert_owner_invariant(db, workspace.id, identity(people,'owner'))


@pytest.mark.parametrize('method', ['PATCH','DELETE'])
def test_admin_cannot_modify_or_remove_admins(client, people, workspace, method):
    sign_in(client, people, 'admin')
    path = endpoint(workspace)+f'/members/{identity(people,"admin")}'
    response = client.request(method,path,json={'role':'member'} if method == 'PATCH' else None)
    assert response.status_code == 403


def test_owner_can_demote_admin(client, people, workspace):
    response = client.patch(endpoint(workspace)+f'/members/{identity(people,"admin")}', json={'role':'member'})
    assert response.status_code == 200 and response.json()['role'] == 'member'


@pytest.mark.parametrize('role,status', [('owner',204),('admin',204),('member',403)])
def test_remove_ordinary_member(client, db, people, workspace, role, status):
    sign_in(client, people, role)
    target_id = identity(people,'member')
    response = client.delete(endpoint(workspace)+f'/members/{target_id}')
    assert response.status_code == status
    record = db.scalar(select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace.id,
                                                    WorkspaceMember.user_id == target_id))
    assert (record is None) == (status == 204)
    if status == 204:
        sign_in(client, people, 'member')
        assert client.get(endpoint(workspace)).status_code == 404
        assert client.get(BASE+'/').json() == []


@pytest.mark.parametrize('role', ['owner','admin'])
@pytest.mark.parametrize('method', ['PATCH','DELETE'])
def test_owner_cannot_be_removed_or_demoted(client, db, people, workspace, role, method):
    sign_in(client, people, role)
    path = endpoint(workspace)+f'/members/{identity(people,"owner")}'
    response = client.request(method,path,json={'role':'admin'} if method == 'PATCH' else None)
    assert response.status_code == 409
    assert_owner_invariant(db,workspace.id,identity(people,'owner'))


@pytest.mark.parametrize('role,status', [('owner',200),('admin',403),('member',403)])
def test_transfer_ownership_permissions(client, db, people, workspace, role, status):
    sign_in(client, people, role)
    response = client.post(endpoint(workspace)+'/transfer-ownership',
                           json={'new_owner_id':str(identity(people,'member'))})
    assert response.status_code == status
    target = 'member' if status == 200 else 'owner'
    assert_owner_invariant(db,workspace.id,identity(people,target))
    if status == 200:
        assert response.json()['owner_id'] == str(identity(people,'member'))
        previous = db.scalar(select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace.id,
                                                          WorkspaceMember.user_id == identity(people,'owner')))
        assert previous.role == 'admin'
        assert client.post(endpoint(workspace)+'/transfer-ownership',
                           json={'new_owner_id':str(identity(people,'admin'))}).status_code == 403
        sign_in(client,people,'member')
        assert client.patch(endpoint(workspace)+f'/members/{identity(people,"owner")}',
                            json={'role':'member'}).status_code == 200


@pytest.mark.parametrize('target,status', [('owner',409),('candidate',404),('missing',404)])
def test_invalid_transfer_target(client, db, people, workspace, target, status):
    target_id = uuid.uuid4() if target == 'missing' else identity(people,target)
    assert client.post(endpoint(workspace)+'/transfer-ownership', json={'new_owner_id':str(target_id)}).status_code == status
    assert_owner_invariant(db,workspace.id,identity(people,'owner'))


def test_transfer_to_inactive_member_rejected(client, db, people, workspace):
    people['member'][0].is_active = False
    db.commit()
    response = client.post(endpoint(workspace)+'/transfer-ownership',
                           json={'new_owner_id':str(identity(people,'member'))})
    assert response.status_code == 404 and response.json()['detail'] == 'Eligible user not found'
    assert_owner_invariant(db,workspace.id,identity(people,'owner'))


@pytest.mark.parametrize('role,status', [('owner',409),('admin',403),('member',403)])
def test_deletion_with_other_members_is_restricted(client, db, people, workspace, role, status):
    sign_in(client,people,role)
    assert client.delete(endpoint(workspace)).status_code == status
    assert_owner_invariant(db,workspace.id,identity(people,'owner'))


def test_empty_workspace_deletion(client, db, people):
    workspace = workspaces.create_workspace(db,identity(people,'owner'),WorkspaceCreate(name='Empty'))
    workspace_id = workspace.id
    assert client.delete(endpoint(workspace)).status_code == 204
    assert db.get(Workspace,workspace_id) is None
    assert db.scalar(select(WorkspaceMember.id).where(WorkspaceMember.workspace_id == workspace_id)) is None
    assert db.get(User,identity(people,'owner')) is not None


def test_deletion_preserves_documents(client, db, people):
    workspace = workspaces.create_workspace(db,identity(people,'owner'),WorkspaceCreate(name='With document'))
    document = Document(workspace_id=workspace.id,uploaded_by=identity(people,'owner'),
                        original_filename='private.pdf',storage_key='private/test',checksum_sha256='a'*64)
    db.add(document)
    db.commit()
    document_id = document.id
    assert client.delete(endpoint(workspace)).status_code == 409
    db.expire_all()
    assert db.get(Document,document_id).storage_key == 'private/test'
    assert_owner_invariant(db,workspace.id,identity(people,'owner'))


@pytest.mark.parametrize('method,suffix,payload', [('GET','',None),('PATCH','',{'name':'X'}),('DELETE','',None),
    ('GET','/members',None),('POST','/members',{'user_id':str(uuid.uuid4())}),
    ('POST','/transfer-ownership',{'new_owner_id':str(uuid.uuid4())})])
def test_invalid_workspace_uuid(client,method,suffix,payload):
    assert client.request(method,BASE+'/not-a-uuid'+suffix,json=payload).status_code == 422


@pytest.mark.parametrize('method', ['PATCH','DELETE'])
def test_invalid_member_uuid(client, workspace, method):
    assert client.request(method,endpoint(workspace)+'/members/not-a-uuid',
                          json={'role':'member'} if method == 'PATCH' else None).status_code == 422


@pytest.mark.parametrize('method,suffix,payload', [
    ('POST','/',{'name':'X'}),('PATCH','/{workspace}',{'name':'X'}),('DELETE','/{workspace}',None),
    ('POST','/{workspace}/members',{'user_id':'{user}'}),
    ('PATCH','/{workspace}/members/{user}',{'role':'admin'}),
    ('DELETE','/{workspace}/members/{user}',None),
    ('POST','/{workspace}/transfer-ownership',{'new_owner_id':'{user}'}),
])
def test_csrf_on_every_workspace_write(client,people,workspace,method,suffix,payload):
    suffix = suffix.format(workspace=workspace.id,user=identity(people,'member'))
    if payload: payload = {k:v.format(user=identity(people,'member')) for k,v in payload.items()}
    client.headers.pop('X-CSRF-Protection')
    assert client.request(method,BASE+suffix,json=payload).status_code == 403


@pytest.mark.parametrize('method', ['PATCH','DELETE'])
def test_cors_permits_trusted_mutation_preflights(client,workspace,method):
    response = client.options(endpoint(workspace),headers={'Origin':ORIGIN,
        'Access-Control-Request-Method':method,'Access-Control-Request-Headers':'x-csrf-protection,content-type'})
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == ORIGIN
    denied = client.options(endpoint(workspace),headers={'Origin':'https://evil.example',
        'Access-Control-Request-Method':method})
    assert denied.status_code == 400


@pytest.mark.parametrize('query', ['limit=0','limit=101','offset=-1'])
def test_pagination_validation(client,workspace,query):
    assert client.get(BASE+'/?'+query).status_code == 422
    assert client.get(endpoint(workspace)+'/members?'+query).status_code == 422


def test_pagination(client,workspace):
    assert len(client.get(endpoint(workspace)+'/members?limit=1&offset=1').json()) == 1
    assert client.get(endpoint(workspace)+'/members?offset=100').json() == []
    assert client.get(BASE+'/?offset=100').json() == []


def test_failed_owner_membership_insert_rolls_back_workspace(client,db,people):
    before = db.scalar(select(func.count()).select_from(Workspace))
    def fail_owner(session, context, instances):
        if any(isinstance(obj,WorkspaceMember) and obj.role == 'owner' for obj in session.new):
            raise RuntimeError('Injected owner membership failure')
    event.listen(db,'before_flush',fail_owner)
    try:
        response = client.post(BASE+'/',json={'name':'Must roll back'})
        assert response.status_code == 500 and 'Injected' not in response.text
    finally:
        event.remove(db,'before_flush',fail_owner)
    assert db.scalar(select(func.count()).select_from(Workspace)) == before
    assert db.scalar(select(Workspace.id).where(Workspace.name == 'Must roll back')) is None
    assert client.post(BASE+'/',json={'name':'Recovered'}).status_code == 201


def test_failed_transfer_rolls_back_all_three_changes(client,db,people,workspace):
    workspace_id, owner_id = workspace.id, identity(people,'owner')
    def fail_after_writes(session,context):
        raise RuntimeError('Injected transfer failure')
    # Authenticate normally first, then inject failure only in the service transaction.
    original = members.transfer_ownership
    def transfer_with_failure(*args,**kwargs):
        event.listen(db,'after_flush',fail_after_writes,once=True)
        return original(*args,**kwargs)
    from unittest.mock import patch
    with patch.object(members,'transfer_ownership',transfer_with_failure):
        response = client.post(endpoint(workspace)+'/transfer-ownership',
                        json={'new_owner_id':str(identity(people,'member'))})
        assert response.status_code == 500 and 'Injected' not in response.text
    event.remove(db,'after_flush',fail_after_writes)
    assert_owner_invariant(db,workspace_id,owner_id)
    assert client.get(endpoint(workspace)).status_code == 200


def test_fk_conflict_rolls_back_deleted_owner_membership(client,db,people):
    workspace = workspaces.create_workspace(db,identity(people,'owner'),WorkspaceCreate(name='Restricted'))
    workspace_id, owner_id = workspace.id, identity(people,'owner')
    def simulate_dependency(session,context,instances):
        if any(isinstance(obj,Workspace) for obj in session.deleted):
            raise IntegrityError('private constraint details',{},RuntimeError('private'))
    event.listen(db,'before_flush',simulate_dependency)
    try:
        response = client.delete(endpoint(workspace))
    finally:
        event.remove(db,'before_flush',simulate_dependency)
    assert response.status_code == 409 and 'private' not in response.text
    assert_owner_invariant(db,workspace_id,owner_id)


def test_legacy_workspace_without_membership_fails_closed(client,db,people):
    workspace = Workspace(name='Legacy',owner_id=identity(people,'owner'))
    db.add(workspace)
    db.commit()
    assert client.get(endpoint(workspace)).status_code == 404
    assert client.get(BASE+'/').json() == []


def test_inconsistent_owner_memberships_are_not_repaired(client,db,people,workspace):
    admin = db.scalar(select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace.id,
                                                   WorkspaceMember.user_id == identity(people,'admin')))
    admin.role = 'owner'
    db.commit()
    response = client.patch(endpoint(workspace),json={'name':'Cannot mutate inconsistent workspace'})
    assert response.status_code == 409
    db.refresh(admin)
    assert admin.role == 'owner'
    assert client.get(endpoint(workspace)).json()['name'] == 'Research'


@pytest.mark.parametrize('method', ['PATCH','DELETE'])
def test_missing_member(client,people,workspace,method):
    response = client.request(method,endpoint(workspace)+f'/members/{identity(people,"outsider")}',
                              json={'role':'member'} if method == 'PATCH' else None)
    assert response.status_code == 404 and response.json()['detail'] == 'Member not found'


def test_inactive_authenticated_user_denied(client,db,people,workspace):
    people['owner'][0].is_active = False
    db.commit()
    assert client.get(endpoint(workspace)).status_code == 401
    assert client.post(BASE+'/',json={'name':'Forbidden'}).status_code == 401
