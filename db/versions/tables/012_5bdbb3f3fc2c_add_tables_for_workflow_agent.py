"""add tables for workflow agent

Revision ID: 5bdbb3f3fc2c
Revises: 78ea06acc5d1
Create Date: 2025-04-23 00:01:52.621795
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# ────────── revision identifiers ──────────
revision: str = "5bdbb3f3fc2c"
down_revision: Union[str, None] = "78ea06acc5d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ────────── upgrade ──────────
def upgrade() -> None:
    # pgcrypto for gen_random_uuid()
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    entity_enum = sa.Enum("account", "person", name="entity_enum")  # ← no .create()

    # ── territory ────────────────────────────────────────────────
    op.create_table(
        "territory",
        sa.Column(
            "territory_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("territory_name", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("territory.territory_id"),
        ),
    )

    # ── account_fullcast ────────────────────────────────────────
    op.create_table(
        "account_fullcast",
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("account_name", sa.Text(), nullable=False),
        sa.Column(
            "territory_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("territory.territory_id"),
            nullable=False,
        ),
        sa.Column(
            "parent_account",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("account_fullcast.account_id"),
        ),
        sa.Column("family_id", postgresql.UUID(as_uuid=True)),
    )

    # ── person ──────────────────────────────────────────────────
    op.create_table(
        "person",
        sa.Column(
            "person_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("person_name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), unique=True),
        sa.Column(
            "territory_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("territory.territory_id"),
            nullable=False,
        ),
    )

    # ── move_event ──────────────────────────────────────────────
    op.create_table(
        "move_event",
        sa.Column("move_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("entity_type", entity_enum, nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "from_territory_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("territory.territory_id"),
            nullable=False,
        ),
        sa.Column(
            "to_territory_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("territory.territory_id"),
            nullable=False,
        ),
        sa.Column("committed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("family_flag", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "actor_person_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("person.person_id"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_move_lookup",
        "move_event",
        ["entity_type", "committed", sa.text("created_at DESC")],
    )

    # ── helper view ─────────────────────────────────────────────
    op.execute(
        """
        CREATE OR REPLACE VIEW territory_with_depth AS
        WITH RECURSIVE tpath AS (
            SELECT territory_id,
                   territory_name,
                   parent_id,
                   0 AS depth
            FROM   territory
            WHERE  parent_id IS NULL
            UNION ALL
            SELECT t.territory_id,
                   t.territory_name,
                   t.parent_id,
                   p.depth + 1
            FROM   territory t
            JOIN   tpath    p ON t.parent_id = p.territory_id
        )
        SELECT * FROM tpath;
        """
    )


# ────────── downgrade ──────────
def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS territory_with_depth")
    op.drop_index("ix_move_lookup", table_name="move_event")
    op.drop_table("move_event")
    op.drop_table("person")
    op.drop_table("account_fullcast")
    op.drop_table("territory")
    op.execute('DROP TYPE IF EXISTS "entity_enum"')
