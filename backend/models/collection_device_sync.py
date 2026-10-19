from __future__ import annotations

import enum

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import BaseModel


class CollectionSyncKind(enum.StrEnum):
    REGULAR = "regular"
    SMART = "smart"


class CollectionDeviceSync(BaseModel):
    """A device subscribed to a collection, whose roms it keeps installed."""

    __tablename__ = "collection_device_syncs"
    __table_args__ = (
        UniqueConstraint(
            "device_id",
            "collection_kind",
            "collection_id",
            name="uq_collection_device_syncs_device_collection",
        ),
        Index(
            "ix_collection_device_syncs_collection",
            "collection_kind",
            "collection_id",
        ),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    # Regular and smart collections live in separate tables, so no foreign key;
    # deleting a collection drops its rows through the collections handler.
    collection_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    collection_id: Mapped[int] = mapped_column(Integer, nullable=False)
