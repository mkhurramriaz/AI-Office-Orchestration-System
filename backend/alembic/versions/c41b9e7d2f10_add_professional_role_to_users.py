"""add validated professional roles to users

Revision ID: c41b9e7d2f10
Revises: bf465314acb2
Create Date: 2026-11-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c41b9e7d2f10"
down_revision: Union[str, Sequence[str], None] = "bf465314acb2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "professional_role",
            sa.Enum(
                "FRONTEND_DEVELOPER",
                "BACKEND_DEVELOPER",
                "FULL_STACK_DEVELOPER",
                "AI_ENGINEER",
                "DATA_ENGINEER",
                "DEVOPS_ENGINEER",
                "QA_ENGINEER",
                "SEO_SPECIALIST",
                "DIGITAL_MARKETER",
                "UI_UX_DESIGNER",
                "PROJECT_MANAGER",
                "BUSINESS_ANALYST",
                "CONTENT_WRITER",
                "OPERATIONS_SPECIALIST",
                name="professionalrole",
                native_enum=False,
                length=50,
            ),
            nullable=True,
        ),
    )
    op.create_index(op.f("ix_users_professional_role"), "users", ["professional_role"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_professional_role"), table_name="users")
    op.drop_column("users", "professional_role")
