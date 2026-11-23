"""Canonicalize the ScreenScraper beat 'em up genre on existing ROMs.

Revision ID: 0163_canonical_ss_genre
Revises: 0162_collection_device_syncs
"""

import sqlalchemy as sa
from alembic import op

from utils.database import CustomJSON
from utils.sql_dialect import json_array_contains_value

revision = "0163_canonical_ss_genre"
down_revision = "0162_collection_device_syncs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    alias, canonical = "Beat'em Up", "Beat 'em Up"
    roms = sa.table(
        "roms",
        sa.column("id", sa.Integer),
        sa.column("ss_metadata", CustomJSON()),
        sa.column("updated_at", sa.DateTime),
    )
    conn = op.get_bind()
    candidates = conn.execute(
        sa.select(roms.c.id, roms.c.ss_metadata).where(
            json_array_contains_value(roms.c.ss_metadata["genres"], alias)
        )
    ).all()

    updates = []
    for rom_id, metadata in candidates:
        genres = metadata["genres"]
        if not isinstance(genres, list) or alias not in genres:
            continue
        normalized = []
        for genre in genres:
            if genre in (alias, canonical):
                if canonical in normalized:
                    continue
                genre = canonical
            normalized.append(genre)
        updates.append(
            {"rom_id": rom_id, "metadata": {**metadata, "genres": normalized}}
        )

    if updates:
        # The existing ROM triggers refresh facets and virtual collection membership.
        conn.execute(
            roms.update()
            .where(roms.c.id == sa.bindparam("rom_id"))
            .values(ss_metadata=sa.bindparam("metadata"), updated_at=sa.func.now()),
            updates,
        )


def downgrade() -> None:
    # The canonical spelling is valid on both versions and has no unique inverse.
    pass
