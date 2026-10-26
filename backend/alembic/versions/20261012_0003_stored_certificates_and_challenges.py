"""stored certificates and verifier challenges
Revision ID: 20261012_0003
Revises: 20261012_0002
Create Date: 2026-10-12 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20261012_0003'
down_revision: Union[str, None] = '20261012_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. stored_certificates table
    op.create_table(
        'stored_certificates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('storage_id', sa.String(length=64), nullable=False),
        sa.Column('credential_id', sa.String(length=66), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True),
        sa.Column('document_digest', sa.String(length=66), nullable=False),
        sa.Column('storage_adapter', sa.String(length=32), nullable=False, server_default='filesystem_encrypted'),
        sa.Column('envelope_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('content_type', sa.String(length=64), nullable=False),
        sa.Column('byte_size', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stored_certificates_storage_id'), 'stored_certificates', ['storage_id'], unique=True)
    op.create_index(op.f('ix_stored_certificates_credential_id'), 'stored_certificates', ['credential_id'], unique=False)
    op.create_index(op.f('ix_stored_certificates_document_digest'), 'stored_certificates', ['document_digest'], unique=False)

    # 2. verifier_challenges table
    op.create_table(
        'verifier_challenges',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('challenge_id', sa.String(length=64), nullable=False),
        sa.Column('challenge_hash', sa.String(length=66), nullable=False),
        sa.Column('verifier_session_id', sa.String(length=128), nullable=False),
        sa.Column('credential_fingerprint', sa.String(length=66), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='ISSUED'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_verifier_challenges_challenge_id'), 'verifier_challenges', ['challenge_id'], unique=True)
    op.create_index(op.f('ix_verifier_challenges_challenge_hash'), 'verifier_challenges', ['challenge_hash'], unique=True)
    op.create_index(op.f('ix_verifier_challenges_verifier_session_id'), 'verifier_challenges', ['verifier_session_id'], unique=False)
    op.create_index(op.f('ix_verifier_challenges_credential_fingerprint'), 'verifier_challenges', ['credential_fingerprint'], unique=False)


def downgrade() -> None:
    op.drop_table('verifier_challenges')
    op.drop_table('stored_certificates')
