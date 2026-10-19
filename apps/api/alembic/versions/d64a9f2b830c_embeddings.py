"""Versioned chunk embeddings and indexing jobs

Revision ID: d64a9f2b830c
Revises: c52d8e7a901b
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR

revision = 'd64a9f2b830c'
down_revision = 'c52d8e7a901b'
branch_labels = None
depends_on = None


def upgrade():
    # pgvector is shared infrastructure; never drop it during downgrade.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table('embedding_profiles',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('provider', sa.String(length=16), nullable=False),
    sa.Column('model', sa.String(length=120), nullable=False),
    sa.Column('revision', sa.String(length=80), nullable=False),
    sa.Column('dimensions', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('dimensions >= 8 AND dimensions <= 3072', name=op.f('ck_embedding_profiles_valid_dimensions')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_embedding_profiles')),
    sa.UniqueConstraint('id', 'dimensions', name=op.f('uq_embedding_profiles_id'))
    )
    op.create_table('embedding_jobs',
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('profile_id', sa.String(length=64), nullable=False),
    sa.Column('generation', sa.Uuid(), nullable=False),
    sa.Column('state', sa.String(length=16), server_default='queued', nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('available_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('lease_id', sa.Uuid(), nullable=True),
    sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("state IN ('queued','running','done','failed')", name=op.f('ck_embedding_jobs_valid_state')),
    sa.CheckConstraint('attempts >= 0', name=op.f('ck_embedding_jobs_nonnegative_attempts')),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], name=op.f('fk_embedding_jobs_document_id_documents'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['profile_id'], ['embedding_profiles.id'], name=op.f('fk_embedding_jobs_profile_id_embedding_profiles'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('document_id', 'profile_id', name=op.f('pk_embedding_jobs'))
    )
    op.create_index('ix_embedding_jobs_profile_available', 'embedding_jobs', ['profile_id', 'available_at'], unique=False)
    op.create_table('chunk_embeddings',
    sa.Column('chunk_id', sa.Uuid(), nullable=False),
    sa.Column('profile_id', sa.String(length=64), nullable=False),
    sa.Column('dimensions', sa.Integer(), nullable=False),
    sa.Column('vector', VECTOR(), nullable=True),
    sa.Column('generation', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=16), server_default='pending', nullable=False),
    sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.CheckConstraint("status != 'completed' OR (vector IS NOT NULL AND generated_at IS NOT NULL)", name=op.f('ck_chunk_embeddings_completed_vector')),
    sa.CheckConstraint("status IN ('pending','completed','failed')", name=op.f('ck_chunk_embeddings_valid_status')),
    sa.CheckConstraint('vector IS NULL OR (vector_dims(vector) = dimensions AND vector_norm(vector) > 0)', name=op.f('ck_chunk_embeddings_valid_vector')),
    sa.ForeignKeyConstraint(['chunk_id'], ['document_chunks.id'], name=op.f('fk_chunk_embeddings_chunk_id_document_chunks'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['profile_id', 'dimensions'], ['embedding_profiles.id', 'embedding_profiles.dimensions'], name='fk_chunk_embeddings_profile_dimensions', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('chunk_id', 'profile_id', name=op.f('pk_chunk_embeddings'))
    )
    op.create_index('ix_chunk_embeddings_profile_status', 'chunk_embeddings', ['profile_id', 'status'], unique=False)


def downgrade():
    # Destructive only to new derived embedding data; source chunks remain intact.
    op.drop_index('ix_chunk_embeddings_profile_status', table_name='chunk_embeddings')
    op.drop_table('chunk_embeddings')
    op.drop_index('ix_embedding_jobs_profile_available', table_name='embedding_jobs')
    op.drop_table('embedding_jobs')
    op.drop_table('embedding_profiles')
