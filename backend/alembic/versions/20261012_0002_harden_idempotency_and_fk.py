"""harden idempotency and foreign key provenance

Revision ID: 20261012_0002
Revises: 20261012_0001
Create Date: 2026-10-12 02:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20261012_0002'
down_revision: Union[str, None] = '20261012_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add idempotency_key column and unique index
    op.add_column('credential_versions', sa.Column('idempotency_key', sa.String(length=128), nullable=True))
    op.create_index(op.f('ix_credential_versions_idempotency_key'), 'credential_versions', ['idempotency_key'], unique=True)

    # 2. Update credentials.issuer_id foreign key constraint to ON DELETE RESTRICT
    op.drop_constraint('credentials_issuer_id_fkey', 'credentials', type_='foreignkey')
    op.create_foreign_key('credentials_issuer_id_fkey', 'credentials', 'issuers', ['issuer_id'], ['issuer_id'], ondelete='RESTRICT')

    # 3. Update credential_versions.credential_id foreign key constraint to ON DELETE RESTRICT
    op.drop_constraint('credential_versions_credential_id_fkey', 'credential_versions', type_='foreignkey')
    op.create_foreign_key('credential_versions_credential_id_fkey', 'credential_versions', 'credentials', ['credential_id'], ['credential_id'], ondelete='RESTRICT')


def downgrade() -> None:
    op.drop_constraint('credential_versions_credential_id_fkey', 'credential_versions', type_='foreignkey')
    op.create_foreign_key('credential_versions_credential_id_fkey', 'credential_versions', 'credentials', ['credential_id'], ['credential_id'], ondelete='CASCADE')

    op.drop_constraint('credentials_issuer_id_fkey', 'credentials', type_='foreignkey')
    op.create_foreign_key('credentials_issuer_id_fkey', 'credentials', 'issuers', ['issuer_id'], ['issuer_id'], ondelete='CASCADE')

    op.drop_index(op.f('ix_credential_versions_idempotency_key'), table_name='credential_versions')
    op.drop_column('credential_versions', 'idempotency_key')
