import uuid
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from app.models import User, Workspace, WorkspaceMember, Document


@pytest.fixture
def workspace(db):
    owner = User(email=f'{uuid.uuid4()}@example.test', display_name='Owner')
    workspace = Workspace(name='Research', owner=owner)
    db.add(workspace)
    db.flush()
    return workspace


def test_user_workspace_membership(db, workspace):
    member = WorkspaceMember(workspace=workspace, user=workspace.owner, role='owner')
    db.add(member)
    db.commit()
    db.expire_all()
    assert workspace.owner.is_active
    assert workspace.owner.password_hash is None
    assert member.user == workspace.owner
    assert workspace.members == [member]
    assert workspace.owner.owned_workspaces == [workspace]
    assert workspace.created_at.tzinfo is not None
    assert workspace.owner.updated_at.tzinfo is not None
    assert member.joined_at.tzinfo is not None


def test_duplicate_membership(db, workspace):
    for _ in range(2):
        db.add(WorkspaceMember(workspace_id=workspace.id, user_id=workspace.owner_id))
    with pytest.raises(IntegrityError): db.flush()
    db.rollback()


@pytest.mark.parametrize('kind', ['workspace_owner', 'member_user', 'member_workspace', 'document_workspace', 'document_uploader'])
def test_foreign_keys(db, workspace, kind):
    missing = uuid.uuid4()
    if kind == 'workspace_owner': obj = Workspace(name='Invalid', owner_id=missing)
    elif kind.startswith('member'):
        obj = WorkspaceMember(workspace_id=missing if kind == 'member_workspace' else workspace.id,
                              user_id=missing if kind == 'member_user' else workspace.owner_id)
    else:
        obj = Document(workspace_id=missing if kind == 'document_workspace' else workspace.id,
                       uploaded_by=missing if kind == 'document_uploader' else workspace.owner_id,
                       original_filename='paper.pdf', storage_key='test/paper', checksum_sha256='a'*64)
    db.add(obj)
    with pytest.raises(IntegrityError): db.flush()
    db.rollback()


def test_document_metadata(db, workspace):
    document = Document(workspace=workspace, uploader=workspace.owner, original_filename='paper.pdf',
                        storage_key='private/paper', mime_type='application/pdf', file_size=123, checksum_sha256='a'*64)
    db.add(document)
    db.commit()
    db.expire_all()
    saved = db.scalar(select(Document).where(Document.id == document.id))
    assert saved.storage_key == 'private/paper'
    assert saved.processing_status == 'pending'
    assert saved.file_size == 123
    assert saved.created_at.tzinfo is not None
    assert saved.workspace == workspace
    assert saved.uploader == workspace.owner
    before = saved.updated_at
    saved.processing_status = 'completed'
    db.flush()
    assert saved.updated_at >= before


@pytest.mark.parametrize('field,value', [('processing_status','unknown'), ('file_size',-1), ('checksum_sha256','invalid')])
def test_invalid_document(db, workspace, field, value):
    values = dict(workspace_id=workspace.id, uploaded_by=workspace.owner_id, original_filename='x', storage_key='x', checksum_sha256='a'*64)
    values[field] = value
    db.add(Document(**values))
    with pytest.raises(IntegrityError): db.flush()
    db.rollback()


def test_invalid_role(db, workspace):
    db.add(WorkspaceMember(workspace=workspace, user=workspace.owner, role='superuser'))
    with pytest.raises(IntegrityError): db.flush()
    db.rollback()


@pytest.mark.parametrize('entity', ['owner', 'workspace'])
def test_restrict_deletion(db, workspace, entity):
    db.add(WorkspaceMember(workspace=workspace, user=workspace.owner))
    db.flush()
    db.delete(workspace.owner if entity == 'owner' else workspace)
    with pytest.raises(IntegrityError): db.flush()
    db.rollback()


def test_unique_email(db, workspace):
    db.add(User(email=workspace.owner.email, display_name='Duplicate'))
    with pytest.raises(IntegrityError): db.flush()
    db.rollback()
