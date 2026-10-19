"""Database-backed authentication and case-insensitive email identities.

Revision ID: a31f8c9d204e
Revises: 6cc0ce3f2778
"""
from alembic import op
import sqlalchemy as sa

revision = 'a31f8c9d204e'
down_revision = '6cc0ce3f2778'
branch_labels = None
depends_on = None


def upgrade():
    # Refuse ambiguous legacy identities without changing or merging any accounts.
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM users GROUP BY lower(btrim(email)) HAVING count(*) > 1) THEN
            RAISE EXCEPTION 'Conflicting email identities: resolve explicitly before migrating';
        END IF;
    END $$""")
    op.create_index('uq_users_email_normalized', 'users', [sa.text('lower(btrim(email))')], unique=True)
    op.create_table('auth_sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True)),
        sa.Column('last_used_at', sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint('id', name='pk_auth_sessions'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='RESTRICT', name='fk_auth_sessions_user_id_users'),
        sa.UniqueConstraint('token_hash', name='uq_auth_sessions_token_hash'))
    op.create_index('ix_auth_sessions_user_id', 'auth_sessions', ['user_id'])
    op.create_index('ix_auth_sessions_expires_at', 'auth_sessions', ['expires_at'])
    op.create_table('auth_rate_limits',
        sa.Column('key', sa.String(64), nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('key', 'window_start', name='pk_auth_rate_limits'))


def downgrade():
    op.drop_table('auth_rate_limits')
    op.drop_table('auth_sessions')
    op.drop_index('uq_users_email_normalized', table_name='users')
