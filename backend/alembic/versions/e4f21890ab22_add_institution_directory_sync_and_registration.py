"""add_institution_directory_sync_and_registration

Revision ID: e4f21890ab22
Revises: d2b31e091f48
Create Date: 2026-10-23 01:52:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = 'e4f21890ab22'
down_revision: Union[str, Sequence[str], None] = 'd2b31e091f48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # 1. Add source and last_synced_at to institutions if not present
    inst_cols = [c["name"] for c in inspector.get_columns("institutions")] if "institutions" in inspector.get_table_names() else []
    if "source" not in inst_cols:
        op.add_column('institutions', sa.Column('source', sa.String(length=100), nullable=False, server_default='PORTAL_REGISTRY'))
    if "last_synced_at" not in inst_cols:
        op.add_column('institutions', sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True))

    # 2. Create institution_registration_requests if not present
    if "institution_registration_requests" not in inspector.get_table_names():
        op.create_table(
            'institution_registration_requests',
            sa.Column('id', sa.CHAR(36), primary_key=True),
            sa.Column('institution_name', sa.String(length=255), nullable=False),
            sa.Column('aicte_id', sa.String(length=100), nullable=True),
            sa.Column('contact_person', sa.String(length=255), nullable=False),
            sa.Column('official_email', sa.String(length=255), nullable=False),
            sa.Column('region', sa.String(length=100), nullable=True),
            sa.Column('address', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='pending_verification'),
            sa.Column('reviewed_by', sa.CHAR(36), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('review_decision', sa.String(length=50), nullable=True),
            sa.Column('review_reason', sa.Text(), nullable=True),
            sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('institution_id', sa.CHAR(36), sa.ForeignKey('institutions.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('idx_reg_req_email', 'institution_registration_requests', ['official_email'], unique=False)
        op.create_index('idx_reg_req_status', 'institution_registration_requests', ['status'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    if "institution_registration_requests" in inspector.get_table_names():
        op.drop_table('institution_registration_requests')
    inst_cols = [c["name"] for c in inspector.get_columns("institutions")] if "institutions" in inspector.get_table_names() else []
    if "last_synced_at" in inst_cols:
        op.drop_column('institutions', 'last_synced_at')
    if "source" in inst_cols:
        op.drop_column('institutions', 'source')
