"""add delivery_image to items

Revision ID: c7e1d9f2a4b8
Revises: 91c3856a8aa0
Create Date: 2026-09-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c7e1d9f2a4b8'
down_revision: Union[str, None] = '91c3856a8aa0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("items", sa.Column("delivery_image", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("items", "delivery_image")
