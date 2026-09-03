"""restrict languages to EN, LT, RU

Revision ID: 0d0a515b4b04
Revises: c7e1d9f2a4b8
Create Date: 2026-09-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0d0a515b4b04'
down_revision: Union[str, None] = 'c7e1d9f2a4b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Postgres enum types cannot drop values, so the old values stay in the
        # type; rows using them are reset to EN below.
        with op.get_context().autocommit_block():
            op.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'language') THEN
                        CREATE TYPE language AS ENUM ('EN', 'LT', 'RU');
                    ELSE
                        ALTER TYPE language ADD VALUE IF NOT EXISTS 'LT';
                        ALTER TYPE language ADD VALUE IF NOT EXISTS 'RU';
                    END IF;
                END
                $$;
                """
            )
    op.execute("UPDATE users SET language = 'EN' WHERE language NOT IN ('EN', 'LT', 'RU');")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                """
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'language') THEN
                        ALTER TABLE users ALTER COLUMN language TYPE text USING language::text;
                        DROP TYPE language;
                        UPDATE users SET language = 'EN' WHERE language NOT IN ('EN', 'FR', 'DE', 'IT');
                        CREATE TYPE language AS ENUM ('EN', 'FR', 'DE', 'IT');
                        ALTER TABLE users ALTER COLUMN language TYPE language USING language::language;
                    END IF;
                END
                $$;
                """
            )
    op.execute("UPDATE users SET language = 'EN' WHERE language NOT IN ('EN');")
