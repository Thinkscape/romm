"""The collections a device keeps installed, as the device reconciles them."""

from typing import Annotated

from fastapi import Path as PathVar
from fastapi import Request, status

from decorators.auth import protected_route
from endpoints.responses.collection_sync import DeviceCollectionSchema
from handler.auth.constants import Scope
from handler.auth.dependencies import get_rom_visibility_filter
from handler.database import (
    db_collection_handler,
    db_collection_sync_handler,
    db_rom_handler,
)
from models.collection import Collection, SmartCollection
from models.collection_device_sync import CollectionDeviceSync, CollectionSyncKind
from utils.datetime import to_utc
from utils.router import APIRouter

from .install import _require_device

router = APIRouter()


def _device_collection(
    sync: CollectionDeviceSync, user_id: int
) -> tuple[Collection | SmartCollection, list[int]] | None:
    """The subscribed collection and its members, None once gone or no longer readable."""
    collection: Collection | SmartCollection | None
    if sync.collection_kind == CollectionSyncKind.REGULAR:
        collection = db_collection_handler.get_collection(sync.collection_id)
        rom_ids = sorted(collection.rom_ids) if collection else []
    else:
        collection = db_collection_handler.get_smart_collection(sync.collection_id)
        # The cached membership, maintained on every library and criteria change.
        rom_ids = list(collection.rom_ids) if collection else []
    if collection is None or (
        collection.user_id != user_id and not collection.is_public
    ):
        return None
    return collection, rom_ids


@protected_route(
    router.get,
    "/{device_id}/collections",
    [Scope.DEVICES_READ, Scope.COLLECTIONS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def get_device_collections(
    request: Request,
    device_id: Annotated[str, PathVar(description="Target device id.")],
) -> list[DeviceCollectionSchema]:
    """Every collection the device syncs, with its current members."""
    _require_device(request, device_id)

    resolved = [
        (sync, found)
        for sync in db_collection_sync_handler.get_for_device(device_id)
        if (found := _device_collection(sync, request.user.id)) is not None
    ]

    visibility = get_rom_visibility_filter(request)
    hidden: set[int] = set()
    if not visibility.is_unrestricted:
        all_ids = {rom_id for _, (_, rom_ids) in resolved for rom_id in rom_ids}
        hidden = db_rom_handler.get_hidden_rom_ids_among(list(all_ids), visibility)

    return [
        DeviceCollectionSchema(
            collection_kind=CollectionSyncKind(sync.collection_kind),
            collection_id=sync.collection_id,
            name=collection.name,
            description=collection.description or None,
            rom_ids=[rom_id for rom_id in rom_ids if rom_id not in hidden],
            cover_url=collection.path_cover_large,
            updated_at=max(to_utc(collection.updated_at), to_utc(sync.updated_at)),
        )
        for sync, (collection, rom_ids) in resolved
    ]
