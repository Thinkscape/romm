/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CollectionSyncKind } from './CollectionSyncKind';
export type DeviceCollectionSchema = {
    collection_kind: CollectionSyncKind;
    collection_id: number;
    name: string;
    description: (string | null);
    rom_ids: Array<number>;
    cover_url: (string | null);
    updated_at: string;
};

