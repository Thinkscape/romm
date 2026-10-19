from collections.abc import Iterable, Sequence

from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from decorators.database import INJECTED_SESSION, begin_session
from models.collection_device_sync import CollectionDeviceSync, CollectionSyncKind

from .base_handler import DBBaseHandler


class DBCollectionSyncsHandler(DBBaseHandler):
    @begin_session
    def get_device_ids(
        self,
        user_id: int,
        collection_kind: CollectionSyncKind,
        collection_id: int,
        session: Session = INJECTED_SESSION,
    ) -> list[str]:
        """The user's devices subscribed to the collection, sorted."""
        return sorted(
            session.scalars(
                select(CollectionDeviceSync.device_id).filter_by(
                    user_id=user_id,
                    collection_kind=collection_kind,
                    collection_id=collection_id,
                )
            ).all()
        )

    @begin_session
    def get_subscribed_device_ids(
        self,
        collection_kind: CollectionSyncKind,
        collection_id: int,
        session: Session = INJECTED_SESSION,
    ) -> list[str]:
        """Every device subscribed to the collection, whoever owns it."""
        return sorted(
            session.scalars(
                select(CollectionDeviceSync.device_id).filter_by(
                    collection_kind=collection_kind, collection_id=collection_id
                )
            ).all()
        )

    @begin_session
    def get_for_device(
        self,
        device_id: str,
        session: Session = INJECTED_SESSION,
    ) -> Sequence[CollectionDeviceSync]:
        return session.scalars(
            select(CollectionDeviceSync)
            .filter_by(device_id=device_id)
            .order_by(CollectionDeviceSync.id.asc())
        ).all()

    @begin_session
    def replace_device_ids(
        self,
        user_id: int,
        collection_kind: CollectionSyncKind,
        collection_id: int,
        device_ids: Iterable[str],
        session: Session = INJECTED_SESSION,
    ) -> set[str]:
        """Make the user's subscriptions to the collection exactly ``device_ids``.

        Returns the devices whose subscription changed (added or removed).
        """
        wanted = set(device_ids)
        current = set(
            session.scalars(
                select(CollectionDeviceSync.device_id).filter_by(
                    user_id=user_id,
                    collection_kind=collection_kind,
                    collection_id=collection_id,
                )
            ).all()
        )
        removed = current - wanted
        added = wanted - current
        if removed:
            session.execute(
                delete(CollectionDeviceSync).where(
                    CollectionDeviceSync.user_id == user_id,
                    CollectionDeviceSync.collection_kind == collection_kind,
                    CollectionDeviceSync.collection_id == collection_id,
                    CollectionDeviceSync.device_id.in_(removed),
                )
            )
        if added:
            try:
                with session.begin_nested():
                    session.execute(
                        insert(CollectionDeviceSync),
                        [
                            {
                                "user_id": user_id,
                                "device_id": device_id,
                                "collection_kind": collection_kind,
                                "collection_id": collection_id,
                            }
                            for device_id in sorted(added)
                        ],
                    )
            except IntegrityError:
                # A concurrent request subscribed the same devices; data is consistent.
                pass
        return removed | added
