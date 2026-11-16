"""Durable chain transaction intents and recovery."""
from alembic import op
import sqlalchemy as sa

revision = "20261027_0005"
down_revision = "20261012_0004"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("chain_operations",
        sa.Column("operation_id", sa.String(36), primary_key=True),
        sa.Column("credential_id", sa.String(66), sa.ForeignKey("credentials.credential_id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason_code", sa.Integer(), nullable=False),
        sa.Column("tx_hash", sa.String(66)),
        sa.Column("error", sa.String(1024)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_chain_operations_credential_id", "chain_operations", ["credential_id"])

def downgrade():
    op.drop_table("chain_operations")
