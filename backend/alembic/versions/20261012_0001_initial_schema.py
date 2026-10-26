"""initial schema

Revision ID: 20261012_0001
Revises: 
Create Date: 2026-10-12 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20261012_0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. issuers table
    op.create_table(
        'issuers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('issuer_id', sa.String(length=66), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('metadata_uri', sa.String(length=1024), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='ACTIVE'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_issuers_issuer_id'), 'issuers', ['issuer_id'], unique=True)

    # 2. credentials table
    op.create_table(
        'credentials',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('credential_id', sa.String(length=66), nullable=False),
        sa.Column('issuer_id', sa.String(length=66), nullable=False),
        sa.Column('current_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('current_fingerprint', sa.String(length=66), nullable=False),
        sa.Column('current_status', sa.String(length=32), nullable=False, server_default='ACTIVE'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['issuer_id'], ['issuers.issuer_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_credentials_credential_id'), 'credentials', ['credential_id'], unique=True)
    op.create_index(op.f('ix_credentials_current_fingerprint'), 'credentials', ['current_fingerprint'], unique=True)
    op.create_index(op.f('ix_credentials_issuer_id'), 'credentials', ['issuer_id'], unique=False)

    # 3. credential_versions table
    op.create_table(
        'credential_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('credential_id', sa.String(length=66), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('fingerprint', sa.String(length=66), nullable=False),
        sa.Column('document_digest', sa.String(length=66), nullable=False),
        sa.Column('metadata_digest', sa.String(length=66), nullable=False),
        sa.Column('merkle_root', sa.String(length=66), nullable=False),
        sa.Column('expires_at', sa.BigInteger(), nullable=True, server_default='0'),
        sa.Column('issuance_tx_hash', sa.String(length=66), nullable=True),
        sa.Column('issuance_status', sa.String(length=32), nullable=False, server_default='PENDING'),
        sa.Column('block_number', sa.BigInteger(), nullable=True),
        sa.Column('chain_id', sa.BigInteger(), nullable=True),
        sa.Column('superseded_by_fingerprint', sa.String(length=66), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['credential_id'], ['credentials.credential_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('credential_id', 'version', name='uq_credential_version')
    )
    op.create_index(op.f('ix_credential_versions_credential_id'), 'credential_versions', ['credential_id'], unique=False)
    op.create_index(op.f('ix_credential_versions_fingerprint'), 'credential_versions', ['fingerprint'], unique=True)
    op.create_index(op.f('ix_credential_versions_issuance_tx_hash'), 'credential_versions', ['issuance_tx_hash'], unique=False)

    # 4. audit_events table
    op.create_table(
        'audit_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('entity_type', sa.String(length=64), nullable=False),
        sa.Column('entity_id', sa.String(length=128), nullable=False),
        sa.Column('outcome', sa.String(length=32), nullable=False),
        sa.Column('correlation_id', sa.String(length=64), nullable=False),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_events_correlation_id'), 'audit_events', ['correlation_id'], unique=False)
    op.create_index(op.f('ix_audit_events_entity_id'), 'audit_events', ['entity_id'], unique=False)
    op.create_index(op.f('ix_audit_events_event_type'), 'audit_events', ['event_type'], unique=False)


def downgrade() -> None:
    op.drop_table('audit_events')
    op.drop_table('credential_versions')
    op.drop_table('credentials')
    op.drop_table('issuers')
