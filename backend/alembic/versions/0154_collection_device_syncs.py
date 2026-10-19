"""Add the collection_device_syncs table.

Install requests live in Redis, so their new `action` field needs no column.

Revision ID: 0154_collection_device_syncs
Revises: 0153_play_permissions
Create Date: 2026-10-19 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0154_collection_device_syncs"
down_revision = "0153_play_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collection_device_syncs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=255), nullable=False),
        sa.Column("collection_kind", sa.String(length=16), nullable=False),
        sa.Column("collection_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "device_id",
            "collection_kind",
            "collection_id",
            name="uq_collection_device_syncs_device_collection",
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ix_collection_device_syncs_user_id",
        "collection_device_syncs",
        ["user_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_collection_device_syncs_collection",
        "collection_device_syncs",
        ["collection_kind", "collection_id"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    # The indexes back the foreign keys, so they go with the table.
    op.drop_table("collection_device_syncs", if_exists=True)
