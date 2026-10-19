import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import mitt, { type Emitter } from "mitt";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import type { DeviceSchema } from "@/__generated__";
import type { Events } from "@/types/emitter";
import CollectionSyncDialog from "./CollectionSyncDialog.vue";

const {
  fetchDevices,
  fetchOnlineDeviceIds,
  fetchCollectionSync,
  updateCollectionSync,
} = vi.hoisted(() => ({
  fetchDevices: vi.fn(),
  fetchOnlineDeviceIds: vi.fn(),
  fetchCollectionSync: vi.fn(),
  updateCollectionSync: vi.fn(),
}));

vi.mock("vue-i18n");

vi.mock("@/services/api/device", () => ({
  default: { fetchDevices, fetchOnlineDeviceIds },
}));

vi.mock("@/services/api/collection-sync", () => ({
  default: { fetchCollectionSync, updateCollectionSync },
}));

vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ mdAndUp: ref(true) }),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ error: vi.fn(), success: vi.fn() }),
}));

function device(id: string, collectionSync = true): DeviceSchema {
  return {
    id,
    name: id,
    capabilities: collectionSync ? { collection_sync: true } : null,
    last_seen: null,
  } as DeviceSchema;
}

function mountDialog(emitter: Emitter<Events>): VueWrapper {
  return mount(CollectionSyncDialog, {
    global: {
      provide: { emitter },
      stubs: {
        RDialog: {
          props: { modelValue: { type: Boolean, default: false } },
          emits: ["update:modelValue", "close"],
          template: `<div v-if="modelValue">
            <slot name="content" />
            <slot name="footer" />
          </div>`,
        },
        RCheckbox: {
          props: {
            modelValue: { type: Boolean, default: false },
            disabled: { type: Boolean, default: false },
          },
          emits: ["update:modelValue"],
          template: `<label data-test-device>
            <input type="checkbox" :checked="modelValue" :disabled="disabled"
              @change="$emit('update:modelValue', $event.target.checked)" />
            <slot />
          </label>`,
        },
        RBtn: true,
        RIcon: true,
        RSpinner: { template: "<div data-test-spinner />" },
        REmptyState: true,
      },
    },
  });
}

describe("CollectionSyncDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchOnlineDeviceIds.mockResolvedValue({ data: ["deck"] });
    fetchCollectionSync.mockResolvedValue({
      data: {
        collection_kind: "regular",
        collection_id: 3,
        device_ids: ["thor"],
      },
    });
  });

  it("replaces the spinner with the syncable devices once loaded", async () => {
    fetchDevices.mockResolvedValue({
      data: [device("deck"), device("thor"), device("old-phone", false)],
    });
    const emitter = mitt<Events>();
    const wrapper = mountDialog(emitter);

    emitter.emit("showCollectionSyncDialog", {
      kind: "regular",
      id: 3,
      name: "E2E Test Picks",
    });
    await flushPromises();

    expect(wrapper.find("[data-test-spinner]").exists()).toBe(false);
    const rows = wrapper.findAll("[data-test-device]");
    expect(rows.map((row) => row.text())).toEqual(["deck", "thor"]);
    const checked = rows.map(
      (row) => (row.find("input").element as HTMLInputElement).checked,
    );
    expect(checked).toEqual([false, true]);
    expect(fetchCollectionSync).toHaveBeenCalledWith("regular", 3);
  });
});
