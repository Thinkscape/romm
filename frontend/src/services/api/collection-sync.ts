import type {
  CollectionSyncKind,
  CollectionSyncPayload,
  CollectionSyncSchema,
} from "@/__generated__";
import api from "@/services/api";

async function fetchCollectionSync(
  collectionKind: CollectionSyncKind,
  collectionId: number,
) {
  return api.get<CollectionSyncSchema>("/collection-syncs", {
    params: { collection_kind: collectionKind, collection_id: collectionId },
  });
}

async function updateCollectionSync(payload: CollectionSyncPayload) {
  return api.put<CollectionSyncSchema>("/collection-syncs", payload);
}

export default {
  fetchCollectionSync,
  updateCollectionSync,
};
