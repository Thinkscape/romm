"""Which of the user's devices keep a collection installed ("Sync to device")."""

from typing import Annotated

from fastapi import HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from decorators.auth import protected_route
from endpoints.responses.collection_sync import CollectionSyncSchema
from endpoints.sockets.devices import emit_collections_changed
from exceptions.endpoint_exceptions import (
    CollectionNotFoundInDatabaseException,
    CollectionPermissionError,
)
from handler.auth.constants import Scope
from handler.database import (
    db_collection_handler,
    db_collection_sync_handler,
    db_device_handler,
)
from handler.device_install.policy import accepts_collection_sync
from logger.logger import log
from models.collection_device_sync import CollectionSyncKind
from utils.auth import token_device_id
from utils.router import APIRouter

router = APIRouter(
    prefix="/collection-syncs",
    tags=["collections"],
)

MAX_SYNCED_DEVICES = 64


class CollectionSyncPayload(BaseModel):
    collection_kind: CollectionSyncKind
    collection_id: int = Field(ge=1)
    device_ids: list[str] = Field(max_length=MAX_SYNCED_DEVICES)


def _require_readable_collection(
    request: Request, collection_kind: CollectionSyncKind, collection_id: int
) -> None:
    """404 for a missing collection, 403 for another user's private one."""
    collection = (
        db_collection_handler.get_collection(collection_id)
        if collection_kind == CollectionSyncKind.REGULAR
        else db_collection_handler.get_smart_collection(collection_id)
    )
    if collection is None:
        raise CollectionNotFoundInDatabaseException(collection_id)
    if collection.user_id != request.user.id and not collection.is_public:
        raise CollectionPermissionError(collection_id)


def _visible_device_ids(request: Request, device_ids: list[str]) -> list[str]:
    """A device-bound token sees only its own device's subscription."""
    bound_device_id = token_device_id(request)
    if bound_device_id is None:
        return device_ids
    return [device_id for device_id in device_ids if device_id == bound_device_id]


@protected_route(
    router.get,
    "",
    [Scope.DEVICES_READ, Scope.COLLECTIONS_READ],
    responses={status.HTTP_403_FORBIDDEN: {}, status.HTTP_404_NOT_FOUND: {}},
)
def get_collection_sync(
    request: Request,
    collection_kind: Annotated[
        CollectionSyncKind, Query(description="Kind of collection.")
    ],
    collection_id: Annotated[int, Query(description="Collection id.", ge=1)],
) -> CollectionSyncSchema:
    """The caller's devices subscribed to a collection."""
    _require_readable_collection(request, collection_kind, collection_id)
    device_ids = db_collection_sync_handler.get_device_ids(
        user_id=request.user.id,
        collection_kind=collection_kind,
        collection_id=collection_id,
    )
    return CollectionSyncSchema(
        collection_kind=collection_kind,
        collection_id=collection_id,
        device_ids=_visible_device_ids(request, device_ids),
    )


@protected_route(
    router.put,
    "",
    [Scope.DEVICES_WRITE, Scope.COLLECTIONS_READ],
    responses={
        status.HTTP_400_BAD_REQUEST: {},
        status.HTTP_403_FORBIDDEN: {},
        status.HTTP_404_NOT_FOUND: {},
    },
)
async def update_collection_sync(
    request: Request,
    payload: CollectionSyncPayload,
) -> CollectionSyncSchema:
    """Replace the caller's devices subscribed to a collection."""
    _require_readable_collection(
        request, payload.collection_kind, payload.collection_id
    )

    bound_device_id = token_device_id(request)
    owned = {
        device.id: device
        for device in db_device_handler.get_devices(user_id=request.user.id)
        if bound_device_id is None or device.id == bound_device_id
    }
    wanted = set(payload.device_ids)
    for device_id in sorted(wanted):
        device = owned.get(device_id)
        if device is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Device {device_id} is not one of your devices",
            )
        if not accepts_collection_sync(device.capabilities):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Device {device_id} does not accept collection sync",
            )

    current = db_collection_sync_handler.get_device_ids(
        user_id=request.user.id,
        collection_kind=payload.collection_kind,
        collection_id=payload.collection_id,
    )
    if bound_device_id is not None:
        # A device manages only its own subscription, leaving its siblings'.
        wanted |= {device_id for device_id in current if device_id != bound_device_id}

    changed = db_collection_sync_handler.replace_device_ids(
        user_id=request.user.id,
        collection_kind=payload.collection_kind,
        collection_id=payload.collection_id,
        device_ids=wanted,
    )
    if changed:
        log.info(
            f"Collection {payload.collection_kind}:{payload.collection_id} now syncs "
            f"to devices {sorted(wanted)}"
        )
        await emit_collections_changed(changed)

    return CollectionSyncSchema(
        collection_kind=payload.collection_kind,
        collection_id=payload.collection_id,
        device_ids=_visible_device_ids(request, sorted(wanted)),
    )
