<script setup lang="ts">
// Picks which of the user's devices keep a collection installed. The device
// installs every member, follows membership changes, and mirrors the
// collection in its launcher; the server only stores the subscription set.
import { RBtn, RCheckbox, RDialog, REmptyState, RSpinner } from "@v2/lib";
import { computed, ref, shallowRef } from "vue";
import { useI18n } from "vue-i18n";
import type { DeviceSchema } from "@/__generated__";
import collectionSyncApi from "@/services/api/collection-sync";
import deviceApi from "@/services/api/device";
import type { Events } from "@/types/emitter";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useEmitterEvent } from "@/v2/composables/useEmitterEvent";
import { useIsAlive } from "@/v2/composables/useIsAlive";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { errorMessage } from "@/v2/utils/errorMessage";

defineOptions({ inheritAttrs: false });

type Target = Events["showCollectionSyncDialog"];

const { t } = useI18n();
const { mdAndUp } = useBreakpoint();
const snackbar = useSnackbar();
const alive = useIsAlive();

const show = ref(false);
// shallowRef: a deep ref would store a reactive proxy of the event payload,
// so the identity check in isCurrent() would never match the raw object.
const target = shallowRef<Target | null>(null);
const loading = ref(false);
const saving = ref(false);
const loadError = ref<string | null>(null);
const devices = ref<DeviceSchema[]>([]);
const onlineIds = ref(new Set<string>());
const selected = ref(new Set<string>());

const syncableDevices = computed(() =>
  devices.value
    .filter((device) => device.capabilities?.collection_sync === true)
    .sort(
      (a, b) =>
        (b.last_seen ? Date.parse(b.last_seen) : 0) -
        (a.last_seen ? Date.parse(a.last_seen) : 0),
    ),
);

function isCurrent(requested: Target): boolean {
  return alive.value && target.value === requested;
}

async function load(requested: Target) {
  loading.value = true;
  loadError.value = null;
  try {
    const [devicesResponse, onlineResponse, syncResponse] = await Promise.all([
      deviceApi.fetchDevices(),
      deviceApi.fetchOnlineDeviceIds(),
      collectionSyncApi.fetchCollectionSync(requested.kind, requested.id),
    ]);
    if (!isCurrent(requested)) return;
    devices.value = devicesResponse.data;
    onlineIds.value = new Set(onlineResponse.data);
    selected.value = new Set(syncResponse.data.device_ids);
  } catch (error) {
    if (isCurrent(requested)) loadError.value = errorMessage(error);
  } finally {
    if (isCurrent(requested)) loading.value = false;
  }
}

useEmitterEvent("showCollectionSyncDialog", (requested) => {
  target.value = requested;
  devices.value = [];
  onlineIds.value = new Set();
  selected.value = new Set();
  show.value = true;
  void load(requested);
});

function toggle(device: DeviceSchema, checked: boolean) {
  if (checked) selected.value.add(device.id);
  else selected.value.delete(device.id);
}

async function save() {
  const requested = target.value;
  if (!requested || saving.value) return;
  saving.value = true;
  try {
    // Only devices that can still sync are sent: a subscription left on a
    // device that lost the capability would make the server refuse the set.
    const syncable = new Set(syncableDevices.value.map((device) => device.id));
    await collectionSyncApi.updateCollectionSync({
      collection_kind: requested.kind,
      collection_id: requested.id,
      device_ids: [...selected.value].filter((id) => syncable.has(id)),
    });
    if (!alive.value) return;
    snackbar.success(
      t("collection.sync-to-device-saved", { name: requested.name }),
      { icon: "mdi-check-bold" },
    );
    if (target.value === requested) closeDialog();
  } catch (error) {
    if (!alive.value) return;
    snackbar.error(
      t("collection.sync-to-device-save-failed", {
        error: errorMessage(error),
      }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    saving.value = false;
  }
}

function retry() {
  if (target.value) void load(target.value);
}

function deviceName(device: DeviceSchema): string {
  return device.name || device.hostname || device.id;
}

function closeDialog() {
  show.value = false;
  target.value = null;
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-cellphone-link"
    :width="mdAndUp ? 440 : '95vw'"
    cancelable
    @close="closeDialog"
  >
    <template #header>
      <div class="r-v2-collection-sync__head">
        <span class="r-v2-collection-sync__title">
          {{ t("collection.sync-to-device") }}
        </span>
        <span v-if="target" class="r-v2-collection-sync__subtitle">
          {{ target.name }}
        </span>
      </div>
    </template>

    <template #content>
      <div v-if="loading" class="r-v2-collection-sync__loading">
        <RSpinner />
      </div>
      <REmptyState
        v-else-if="loadError !== null"
        variant="boxed"
        size="small"
        icon="mdi-alert-circle-outline"
        :title="t('collection.sync-to-device-load-failed')"
        :hint="loadError"
      >
        <template #actions>
          <RBtn variant="flat" prepend-icon="mdi-refresh" @click="retry">
            {{ t("common.try-again") }}
          </RBtn>
        </template>
      </REmptyState>
      <REmptyState
        v-else-if="syncableDevices.length === 0"
        variant="boxed"
        size="small"
        icon="mdi-cellphone-off"
        :hint="t('collection.sync-to-device-empty')"
      />
      <template v-else>
        <p class="r-v2-collection-sync__hint">
          {{ t("collection.sync-to-device-hint") }}
        </p>
        <ul class="r-v2-collection-sync__list">
          <li v-for="device in syncableDevices" :key="device.id">
            <RCheckbox
              variant="card"
              :model-value="selected.has(device.id)"
              :disabled="saving"
              @update:model-value="toggle(device, $event)"
            >
              <span class="r-v2-collection-sync__name">
                <span
                  class="r-v2-collection-sync__presence"
                  :class="{
                    'r-v2-collection-sync__presence--online': onlineIds.has(
                      device.id,
                    ),
                  }"
                  role="img"
                  :aria-label="
                    onlineIds.has(device.id)
                      ? t('common.online')
                      : t('common.offline')
                  "
                />
                {{ deviceName(device) }}
              </span>
            </RCheckbox>
          </li>
        </ul>
      </template>
    </template>

    <template #footer>
      <RBtn
        variant="flat"
        color="primary"
        prepend-icon="mdi-content-save"
        :loading="saving"
        :disabled="loading || loadError !== null || saving"
        @click="save"
      >
        {{ t("common.save") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-collection-sync__head {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-1);
  min-width: 0;
}
.r-v2-collection-sync__title {
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-overlay-fg);
}
.r-v2-collection-sync__subtitle {
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-collection-sync__loading {
  display: grid;
  place-items: center;
  padding: var(--r-space-6);
}
.r-v2-collection-sync__hint {
  margin: 0 0 var(--r-space-3);
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}
.r-v2-collection-sync__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
  max-height: 360px;
  overflow-y: auto;
}
.r-v2-collection-sync__list :deep(.r-checkbox-wrap) {
  display: flex;
}
.r-v2-collection-sync__name {
  display: inline-flex;
  align-items: center;
  gap: var(--r-space-2);
}
.r-v2-collection-sync__presence {
  width: var(--r-space-2);
  height: var(--r-space-2);
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--r-color-fg-faint);
}
.r-v2-collection-sync__presence--online {
  background: var(--r-color-success);
}
</style>
