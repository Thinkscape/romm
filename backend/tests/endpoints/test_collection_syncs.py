from unittest.mock import AsyncMock

import pytest
from fastapi import status
from tests.factories import make_device_token, make_rom

from endpoints import collection_syncs as collection_syncs_endpoints
from endpoints import collections as collections_endpoints
from handler.database import (
    db_collection_handler,
    db_collection_sync_handler,
    db_device_handler,
)
from models.collection import Collection, SmartCollection
from models.collection_device_sync import CollectionSyncKind
from models.device import Device
from models.rom import Rom
from models.user import User

SYNCING = {"remote_install": True, "collection_sync": True}
DEVICE_SCOPES = "devices.read devices.write roms.read collections.read"


@pytest.fixture(autouse=True)
def emits(mocker):
    return {
        "syncs": mocker.patch.object(
            collection_syncs_endpoints, "emit_collections_changed", AsyncMock()
        ),
        "collections": mocker.patch.object(
            collections_endpoints, "emit_collections_changed", AsyncMock()
        ),
    }


def _device(user: User, device_id: str, capabilities: dict[str, bool] | None):
    return db_device_handler.add_device(
        Device(id=device_id, user_id=user.id, name=device_id, capabilities=capabilities)
    )


@pytest.fixture
def deck(admin_user: User) -> Device:
    return _device(admin_user, "deck", SYNCING)


@pytest.fixture
def thor(admin_user: User) -> Device:
    return _device(admin_user, "thor", SYNCING)


@pytest.fixture
def collection(admin_user: User, rom: Rom) -> Collection:
    created = db_collection_handler.add_collection(
        Collection(
            name="Couch co-op",
            description="Two players",
            is_public=False,
            user_id=admin_user.id,
        )
    )
    return db_collection_handler.add_roms_to_collection(created.id, [rom.id])


@pytest.fixture
def smart_collection(admin_user: User, rom: Rom) -> SmartCollection:
    created = db_collection_handler.add_smart_collection(
        SmartCollection(
            name="This platform",
            description="",
            user_id=admin_user.id,
            filter_criteria={"platform_ids": [rom.platform_id]},
        )
    )
    refreshed = db_collection_handler.refresh_smart_collection(created.id)
    assert refreshed is not None
    return refreshed


def _put(client, headers, kind: str, collection_id: int, device_ids: list[str]):
    return client.put(
        "/api/collection-syncs",
        json={
            "collection_kind": kind,
            "collection_id": collection_id,
            "device_ids": device_ids,
        },
        headers=headers,
    )


def _get(client, headers, kind: str, collection_id: int):
    return client.get(
        "/api/collection-syncs",
        params={"collection_kind": kind, "collection_id": collection_id},
        headers=headers,
    )


class TestCollectionSyncs:
    def test_put_replaces_the_set_and_get_reads_it_back(
        self, client, headers, deck, thor, collection, emits
    ):
        first = _put(client, headers, "regular", collection.id, ["deck", "thor"])

        assert first.status_code == status.HTTP_200_OK
        assert first.json() == {
            "collection_kind": "regular",
            "collection_id": collection.id,
            "device_ids": ["deck", "thor"],
        }
        assert set(emits["syncs"].await_args.args[0]) == {"deck", "thor"}

        second = _put(client, headers, "regular", collection.id, ["thor"])

        assert second.json()["device_ids"] == ["thor"]
        # Only the device that lost the subscription changed.
        assert set(emits["syncs"].await_args.args[0]) == {"deck"}
        response = _get(client, headers, "regular", collection.id)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["device_ids"] == ["thor"]

    def test_an_unchanged_set_signals_nobody(
        self, client, headers, deck, collection, emits
    ):
        _put(client, headers, "regular", collection.id, ["deck"])
        emits["syncs"].reset_mock()

        _put(client, headers, "regular", collection.id, ["deck"])

        emits["syncs"].assert_not_awaited()

    def test_a_smart_collection_can_be_synced(
        self, client, headers, deck, smart_collection
    ):
        response = _put(client, headers, "smart", smart_collection.id, ["deck"])

        assert response.status_code == status.HTTP_200_OK
        assert _get(client, headers, "smart", smart_collection.id).json()[
            "device_ids"
        ] == ["deck"]

    def test_another_users_device_is_rejected(
        self, client, headers, editor_user, collection, emits
    ):
        _device(editor_user, "editor-deck", SYNCING)

        response = _put(client, headers, "regular", collection.id, ["editor-deck"])

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert db_collection_sync_handler.get_subscribed_device_ids(
            CollectionSyncKind.REGULAR, collection.id
        ) == []
        emits["syncs"].assert_not_awaited()

    def test_an_unknown_device_is_rejected(self, client, headers, collection):
        response = _put(client, headers, "regular", collection.id, ["nope"])

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.parametrize(
        "capabilities", [None, {}, {"remote_install": True}, {"collection_sync": False}]
    )
    def test_a_device_without_collection_sync_is_rejected(
        self, client, headers, admin_user, collection, capabilities
    ):
        _device(admin_user, "plain", capabilities)

        response = _put(client, headers, "regular", collection.id, ["plain"])

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_a_missing_collection_is_not_found(self, client, headers, deck):
        assert (
            _put(client, headers, "regular", 999_999, ["deck"]).status_code
            == status.HTTP_404_NOT_FOUND
        )
        assert (
            _get(client, headers, "smart", 999_999).status_code
            == status.HTTP_404_NOT_FOUND
        )

    def test_another_users_private_collection_is_refused(
        self, client, editor_headers, editor_user, collection
    ):
        _device(editor_user, "editor-deck", SYNCING)

        response = _put(
            client, editor_headers, "regular", collection.id, ["editor-deck"]
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_lists_only_the_callers_devices(
        self, client, headers, editor_headers, editor_user, deck, collection
    ):
        db_collection_handler.update_collection(collection.id, {"is_public": True})
        _device(editor_user, "editor-deck", SYNCING)
        _put(client, headers, "regular", collection.id, ["deck"])
        _put(client, editor_headers, "regular", collection.id, ["editor-deck"])

        assert _get(client, headers, "regular", collection.id).json()[
            "device_ids"
        ] == ["deck"]
        assert _get(client, editor_headers, "regular", collection.id).json()[
            "device_ids"
        ] == ["editor-deck"]

    def test_a_device_token_manages_only_its_own_subscription(
        self, client, headers, admin_user, deck, thor, collection
    ):
        _put(client, headers, "regular", collection.id, ["deck", "thor"])
        _, raw = make_device_token(admin_user, "thor", scopes=DEVICE_SCOPES)
        thor_headers = {"Authorization": f"Bearer {raw}"}

        response = _put(client, thor_headers, "regular", collection.id, [])

        assert response.json()["device_ids"] == []
        assert _get(client, headers, "regular", collection.id).json()[
            "device_ids"
        ] == ["deck"]

    def test_deleting_the_collection_drops_its_subscriptions(
        self, client, headers, deck, collection, emits
    ):
        _put(client, headers, "regular", collection.id, ["deck"])

        response = client.delete(f"/api/collections/{collection.id}", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        assert db_collection_sync_handler.get_subscribed_device_ids(
            CollectionSyncKind.REGULAR, collection.id
        ) == []
        emits["collections"].assert_awaited_with(["deck"])

    def test_deleting_a_smart_collection_drops_its_subscriptions(
        self, client, headers, deck, smart_collection, emits
    ):
        _put(client, headers, "smart", smart_collection.id, ["deck"])

        client.delete(f"/api/collections/smart/{smart_collection.id}", headers=headers)

        assert db_collection_sync_handler.get_subscribed_device_ids(
            CollectionSyncKind.SMART, smart_collection.id
        ) == []
        emits["collections"].assert_awaited_with(["deck"])

    def test_deleting_the_device_drops_its_subscriptions(
        self, client, headers, admin_user, deck, collection
    ):
        _put(client, headers, "regular", collection.id, ["deck"])

        db_device_handler.delete_device(device_id="deck", user_id=admin_user.id)

        assert db_collection_sync_handler.get_for_device("deck") == []


class TestCollectionMutationsSignalDevices:
    @pytest.fixture(autouse=True)
    def subscribed(self, client, headers, deck, collection):
        _put(client, headers, "regular", collection.id, ["deck"])

    def test_adding_roms(self, client, headers, collection, rom, emits, platform):
        other = make_rom(platform, "Second game")

        client.post(
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [other.id]},
            headers=headers,
        )

        emits["collections"].assert_awaited_once_with(["deck"])

    def test_adding_a_rom_already_there_signals_nobody(
        self, client, headers, collection, rom, emits
    ):
        client.post(
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [rom.id]},
            headers=headers,
        )

        emits["collections"].assert_not_awaited()

    def test_renaming(self, mocker, client, headers, collection, rom, emits):
        mocker.patch.object(
            collections_endpoints.fs_resource_handler,
            "get_cover",
            AsyncMock(return_value=("", "")),
        )

        response = client.put(
            f"/api/collections/{collection.id}",
            data={"name": "Renamed", "rom_ids": f"[{rom.id}]"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        emits["collections"].assert_awaited_once_with(["deck"])


class TestDeviceCollections:
    def test_lists_regular_and_smart_collections_with_members(
        self, client, headers, deck, collection, smart_collection, rom
    ):
        _put(client, headers, "regular", collection.id, ["deck"])
        _put(client, headers, "smart", smart_collection.id, ["deck"])

        response = client.get("/api/devices/deck/collections", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        body = sorted(response.json(), key=lambda c: c["collection_kind"])
        assert [
            (c["collection_kind"], c["collection_id"], c["name"], c["rom_ids"])
            for c in body
        ] == [
            ("regular", collection.id, "Couch co-op", [rom.id]),
            ("smart", smart_collection.id, "This platform", [rom.id]),
        ]
        assert body[0]["description"] == "Two players"
        assert body[0]["cover_url"] is None
        assert body[1]["cover_url"] is None
        assert body[1]["description"] is None
        assert all(c["updated_at"] for c in body)

    def test_a_device_token_reads_its_own_list(
        self, client, headers, admin_user, deck, collection, rom
    ):
        _put(client, headers, "regular", collection.id, ["deck"])
        _, raw = make_device_token(admin_user, "deck", scopes=DEVICE_SCOPES)

        response = client.get(
            "/api/devices/deck/collections",
            headers={"Authorization": f"Bearer {raw}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert [c["collection_id"] for c in response.json()] == [collection.id]

    def test_a_device_token_cannot_read_a_sibling(
        self, client, admin_user, deck, thor
    ):
        _, raw = make_device_token(admin_user, "thor", scopes=DEVICE_SCOPES)

        response = client.get(
            "/api/devices/deck/collections",
            headers={"Authorization": f"Bearer {raw}"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_a_device_token_without_collections_read_is_refused(
        self, client, admin_user, deck
    ):
        _, raw = make_device_token(admin_user, "deck")

        response = client.get(
            "/api/devices/deck/collections",
            headers={"Authorization": f"Bearer {raw}"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_another_users_device_is_not_found(self, client, editor_headers, deck):
        response = client.get("/api/devices/deck/collections", headers=editor_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_a_collection_made_private_drops_out_for_other_users(
        self, client, headers, editor_headers, editor_user, collection
    ):
        db_collection_handler.update_collection(collection.id, {"is_public": True})
        _device(editor_user, "editor-deck", SYNCING)
        _put(client, editor_headers, "regular", collection.id, ["editor-deck"])
        db_collection_handler.update_collection(collection.id, {"is_public": False})

        response = client.get(
            "/api/devices/editor-deck/collections", headers=editor_headers
        )

        assert response.json() == []

    def test_a_subscription_change_moves_updated_at(
        self, client, headers, deck, thor, collection
    ):
        _put(client, headers, "regular", collection.id, ["deck"])
        before = client.get("/api/devices/deck/collections", headers=headers).json()[0]

        _put(client, headers, "regular", collection.id, [])
        _put(client, headers, "regular", collection.id, ["deck"])
        after = client.get("/api/devices/deck/collections", headers=headers).json()[0]

        assert after["updated_at"] >= before["updated_at"]
