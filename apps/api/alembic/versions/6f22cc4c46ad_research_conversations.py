"""Private research conversations and saved citations

Revision ID: 6f22cc4c46ad
Revises: d64a9f2b830c
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = '6f22cc4c46ad'
down_revision = 'd64a9f2b830c'
branch_labels = None
depends_on = None


def upgrade():
    # Reviewed additive schema: existing tables and records remain untouched.
    op.create_table('conversations',
    sa.Column('workspace_id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('last_activity_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('next_sequence', sa.Integer(), server_default='1', nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('length(btrim(title)) BETWEEN 1 AND 200', name=op.f('ck_conversations_valid_title')),
    sa.CheckConstraint('next_sequence >= 1 AND mod(next_sequence, 2) = 1', name=op.f('ck_conversations_valid_sequence')),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_conversations_owner_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name=op.f('fk_conversations_workspace_id_workspaces'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_conversations'))
    )
    op.create_index('ix_conversations_owner_created', 'conversations', ['workspace_id', 'owner_id', 'created_at', 'id'], unique=False)
    op.create_table('messages',
    sa.Column('conversation_id', sa.Uuid(), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('generation_status', sa.String(length=16), nullable=False),
    sa.Column('answer_status', sa.String(length=32), nullable=True),
    sa.Column('reason', sa.String(length=80), nullable=True),
    sa.Column('model_identifier', sa.String(length=240), nullable=True),
    sa.Column('usage', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('claims', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('retrieved_evidence_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('request_id', sa.Uuid(), nullable=True),
    sa.Column('generation_http_status', sa.Integer(), nullable=True),
    sa.Column('idempotency_key', sa.Uuid(), nullable=True),
    sa.Column('request_fingerprint', sa.String(length=64), nullable=True),
    sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("(role = 'user' AND mod(sequence, 2) = 1 AND generation_status = 'completed' AND length(content) > 0 AND idempotency_key IS NOT NULL AND request_fingerprint IS NOT NULL AND answer_status IS NULL AND lease_expires_at IS NULL) OR (role = 'assistant' AND mod(sequence, 2) = 0 AND idempotency_key IS NULL AND request_fingerprint IS NULL)", name=op.f('ck_messages_role_fields')),
    sa.CheckConstraint("answer_status IS NULL OR answer_status IN ('answered','insufficient_evidence','retrieval_unavailable','provider_error')", name=op.f('ck_messages_valid_answer_status')),
    sa.CheckConstraint("generation_status IN ('pending','completed','failed')", name=op.f('ck_messages_valid_generation_status')),
    sa.CheckConstraint("role != 'assistant' OR (generation_status = 'pending' AND answer_status IS NULL AND content = '' AND lease_expires_at IS NOT NULL) OR (generation_status != 'pending' AND answer_status IS NOT NULL AND length(content) > 0 AND lease_expires_at IS NULL)", name=op.f('ck_messages_terminal_fields')),
    sa.CheckConstraint("role IN ('user','assistant')", name=op.f('ck_messages_valid_role')),
    sa.CheckConstraint('sequence > 0', name=op.f('ck_messages_positive_sequence')),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], name=op.f('fk_messages_conversation_id_conversations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_messages')),
    sa.UniqueConstraint('conversation_id', 'idempotency_key', name='uq_messages_conversation_key'),
    sa.UniqueConstraint('conversation_id', 'sequence', name='uq_messages_conversation_sequence')
    )
    op.create_index('ix_messages_one_pending', 'messages', ['conversation_id'], unique=True, postgresql_where=sa.text("generation_status = 'pending'"))
    op.create_table('message_citations',
    sa.Column('message_id', sa.Uuid(), nullable=False),
    sa.Column('document_id', sa.Uuid(), nullable=True),
    sa.Column('chunk_id', sa.Uuid(), nullable=True),
    sa.Column('original_document_id', sa.Uuid(), nullable=False),
    sa.Column('original_chunk_id', sa.Uuid(), nullable=False),
    sa.Column('citation_id', sa.String(length=4), nullable=False),
    sa.Column('supporting_excerpt', sa.Text(), nullable=False),
    sa.Column('filename', sa.String(length=1024), nullable=False),
    sa.Column('page_number', sa.Integer(), nullable=True),
    sa.Column('section', sa.String(length=200), nullable=True),
    sa.Column('source_ref', sa.String(length=200), nullable=False),
    sa.Column('char_start', sa.Integer(), nullable=False),
    sa.Column('char_end', sa.Integer(), nullable=False),
    sa.Column('ordering', sa.Integer(), nullable=False),
    sa.Column('validation_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("citation_id ~ '^C[1-9][0-9]?$'", name=op.f('ck_message_citations_valid_identifier')),
    sa.CheckConstraint('char_start >= 0 AND char_end > char_start', name=op.f('ck_message_citations_valid_offsets')),
    sa.CheckConstraint('ordering >= 0', name=op.f('ck_message_citations_nonnegative_ordering')),
    sa.ForeignKeyConstraint(['chunk_id'], ['document_chunks.id'], name=op.f('fk_message_citations_chunk_id_document_chunks'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_message_citations_document_id_documents'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], name=op.f('fk_message_citations_message_id_messages'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_message_citations')),
    sa.UniqueConstraint('message_id', 'citation_id', name='uq_message_citations_identifier'),
    sa.UniqueConstraint('message_id', 'ordering', name='uq_message_citations_ordering')
    )
    op.create_index(op.f('ix_message_citations_chunk_id'), 'message_citations', ['chunk_id'], unique=False)
    op.create_index(op.f('ix_message_citations_document_id'), 'message_citations', ['document_id'], unique=False)


def downgrade():
    # Destructive to conversation history: do not downgrade a populated deployment.
    op.drop_index(op.f('ix_message_citations_document_id'), table_name='message_citations')
    op.drop_index(op.f('ix_message_citations_chunk_id'), table_name='message_citations')
    op.drop_table('message_citations')
    op.drop_index('ix_messages_one_pending', table_name='messages', postgresql_where=sa.text("generation_status = 'pending'"))
    op.drop_table('messages')
    op.drop_index('ix_conversations_owner_created', table_name='conversations')
    op.drop_table('conversations')
