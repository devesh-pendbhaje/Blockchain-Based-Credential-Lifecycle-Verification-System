"""add verifier_principal to verifier_challenges

Revision ID: 20261012_0004
Revises: 20261012_0003
Create Date: 2026-10-12 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20261012_0004'
down_revision: Union[str, None] = '20261012_0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'verifier_challenges',
        sa.Column('verifier_principal', sa.String(length=256), nullable=False, server_default='')
    )
    op.create_index(
        op.f('ix_verifier_challenges_verifier_principal'),
        'verifier_challenges',
        ['verifier_principal'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_verifier_challenges_verifier_principal'), table_name='verifier_challenges')
    op.drop_column('verifier_challenges', 'verifier_principal')
