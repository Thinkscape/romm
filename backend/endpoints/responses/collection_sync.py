from models.collection_device_sync import CollectionSyncKind

from .base import BaseModel, UTCDatetime


class CollectionSyncSchema(BaseModel):
    """The caller's devices that keep a collection installed."""

    collection_kind: CollectionSyncKind
    collection_id: int
    device_ids: list[str]


class DeviceCollectionSchema(BaseModel):
    """A collection a device syncs, as the device reconciles it."""

    collection_kind: CollectionSyncKind
    collection_id: int
    name: str
    description: str | None
    rom_ids: list[int]
    # Server-relative, fetchable with the device's own token; None without artwork.
    cover_url: str | None
    # Moves whenever the name, description, cover, members or subscription change.
    updated_at: UTCDatetime
