"""Add isolated expiring registration requests; existing identities/sessions unchanged.

Revision ID: 91e2b6d8c410
Revises: 6f22cc4c46ad
"""
from alembic import op
import sqlalchemy as sa
revision='91e2b6d8c410'
down_revision='6f22cc4c46ad'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('registration_intents',
        sa.Column('id',sa.Uuid(),nullable=False),
        sa.Column('email',sa.String(320),nullable=False),
        sa.Column('display_name',sa.String(200),nullable=False),
        sa.Column('password_hash',sa.String(512),nullable=False),
        sa.Column('token_hash',sa.String(64),nullable=False),
        sa.Column('browser_hash',sa.String(64),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.PrimaryKeyConstraint('id',name=op.f('pk_registration_intents')),
        sa.UniqueConstraint('token_hash',name=op.f('uq_registration_intents_token_hash')))
    op.create_index('ix_registration_intents_expires_at','registration_intents',['expires_at'])


def downgrade():
    op.drop_index('ix_registration_intents_expires_at',table_name='registration_intents')
    op.drop_table('registration_intents')
