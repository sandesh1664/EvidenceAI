"""Document ingestion chunks and durable jobs

Revision ID: c52d8e7a901b
Revises: a31f8c9d204e
"""
from alembic import op
import sqlalchemy as sa

revision = 'c52d8e7a901b'
down_revision = 'a31f8c9d204e'
branch_labels = None
depends_on = None


def upgrade():
    # Refuse legacy duplicate identities without rewriting or deleting records.
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM documents GROUP BY workspace_id, checksum_sha256 HAVING count(*) > 1) THEN
            RAISE EXCEPTION 'Duplicate workspace checksums require explicit operator resolution';
        END IF;
    END $$""")
    op.add_column('documents', sa.Column('processing_attempts', sa.Integer(), server_default='0', nullable=False))
    op.add_column('documents', sa.Column('last_processed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint('uq_documents_id_workspace', 'documents', ['id', 'workspace_id'])
    op.create_unique_constraint('uq_documents_workspace_checksum', 'documents', ['workspace_id', 'checksum_sha256'])
    op.create_check_constraint(op.f('ck_documents_nonnegative_attempts'), 'documents', 'processing_attempts >= 0')
    op.create_table('storage_cleanup',
    sa.Column('storage_key', sa.String(length=32), nullable=False),
    sa.Column('available_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('last_error', sa.String(length=200), nullable=True),
    sa.PrimaryKeyConstraint('storage_key', name=op.f('pk_storage_cleanup'))
    )
    op.create_index(op.f('ix_storage_cleanup_available_at'), 'storage_cleanup', ['available_at'], unique=False)
    op.create_table('document_chunks',
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('workspace_id', sa.Uuid(), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('page_number', sa.Integer(), nullable=True),
    sa.Column('section', sa.String(length=200), nullable=True),
    sa.Column('source_ref', sa.String(length=200), nullable=False),
    sa.Column('char_start', sa.Integer(), nullable=False),
    sa.Column('char_end', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('char_start >= 0 AND char_end > char_start', name=op.f('ck_document_chunks_valid_offsets')),
    sa.CheckConstraint('chunk_index >= 0', name=op.f('ck_document_chunks_nonnegative_index')),
    sa.CheckConstraint('length(text) > 0', name=op.f('ck_document_chunks_nonempty_text')),
    sa.CheckConstraint('page_number IS NULL OR page_number > 0', name=op.f('ck_document_chunks_positive_page')),
    sa.ForeignKeyConstraint(['document_id', 'workspace_id'], ['documents.id', 'documents.workspace_id'], name='fk_document_chunks_document_workspace', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_document_chunks_workspace_id_workspaces'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_chunks')),
    sa.UniqueConstraint('document_id', 'chunk_index', name=op.f('uq_document_chunks_document_id'))
    )
    op.create_index(op.f('ix_document_chunks_document_id'), 'document_chunks', ['document_id'], unique=False)
    op.create_index(op.f('ix_document_chunks_workspace_id'), 'document_chunks', ['workspace_id'], unique=False)
    op.create_table('document_jobs',
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('state', sa.String(length=20), server_default='queued', nullable=False),
    sa.Column('available_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('lease_id', sa.Uuid(), nullable=True),
    sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("state IN ('queued','running','done','failed')", name=op.f('ck_document_jobs_valid_state')),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_document_jobs_document_id_documents'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('document_id', name=op.f('pk_document_jobs'))
    )
    op.create_index(op.f('ix_document_jobs_available_at'), 'document_jobs', ['available_at'], unique=False)
    op.create_index(op.f('ix_document_jobs_state'), 'document_jobs', ['state'], unique=False)


def downgrade():
    # Destructive for ingestion data: never downgrade a populated deployment.
    op.drop_table('document_jobs')
    op.drop_table('document_chunks')
    op.drop_table('storage_cleanup')
    op.drop_constraint('uq_documents_workspace_checksum', 'documents', type_='unique')
    op.drop_constraint('uq_documents_id_workspace', 'documents', type_='unique')
    op.drop_constraint(op.f('ck_documents_nonnegative_attempts'), 'documents', type_='check')
    op.drop_column('documents', 'last_processed_at')
    op.drop_column('documents', 'processing_attempts')
