"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-02

Matches the tables SQLModel.metadata.create_all() has been generating from
models/user.py, models/transaction.py, and models/plaid_item.py. This is the
baseline every future migration builds on - if a database already has these
tables (created by the old create_all() startup call), run
`alembic stamp 0001_initial_schema` instead of `alembic upgrade head` to mark
it as up to date without re-running the CREATE TABLEs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("oauth_provider", sa.String(), nullable=True),
        sa.Column("oauth_subject", sa.String(), nullable=True),
        sa.UniqueConstraint("oauth_provider", "oauth_subject", name="uq_user_oauth_identity"),
    )

    op.create_table(
        "transaction",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("merchant", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default="manual"),
        sa.Column("plaid_transaction_id", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_transaction_plaid_transaction_id",
        "transaction",
        ["plaid_transaction_id"],
        unique=True,
    )

    op.create_table(
        "plaiditem",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False, unique=True),
        sa.Column("item_id", sa.String(), nullable=False),
        sa.Column("access_token_encrypted", sa.String(), nullable=False),
        sa.Column("institution_name", sa.String(), nullable=True),
        sa.Column("cursor", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("plaiditem")
    op.drop_index("ix_transaction_plaid_transaction_id", table_name="transaction")
    op.drop_table("transaction")
    op.drop_table("user")
