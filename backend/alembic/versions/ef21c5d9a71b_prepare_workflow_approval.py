"""prepare workflow records for pre-project approval

Revision ID: ef21c5d9a71b
Revises: c41b9e7d2f10
Create Date: 2026-11-26

"""
from typing import Sequence, Union

from alembic import op


revision: str = "ef21c5d9a71b"
down_revision: Union[str, Sequence[str], None] = "c41b9e7d2f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("workflow_executions", "project_id", nullable=True)


def downgrade() -> None:
    # Existing executions were project-bound; reject downgrade if new pending
    # workflow rows have not been cleaned up first.
    op.alter_column("workflow_executions", "project_id", nullable=False)
