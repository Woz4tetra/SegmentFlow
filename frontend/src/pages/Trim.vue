<template>
  <!-- Stage Navigation -->
  <StageNavigation v-if="project" :project="project" />

  <section class="hero">
    <router-link :to="{ name: 'Home' }" class="ghost btn-icon" title="Back to Projects">
      <svg class="icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
        <path d="M15 19l-7-7 7-7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      <span>Back to Projects</span>
    </router-link>
    <div class="hero__text">
      <p class="eyebrow">Stage: Trim</p>
      <h1>Trim & Preview</h1>
      <p class="lede">
        Select the start and end positions. The previews update to show the chosen start and end frames. Click "Start Manual Labeling" to proceed.
      </p>
    </div>
  </section>

  <section class="content">
    <div class="trim-layout">
      <div class="trim-card">
        <div v-if="loading" class="loading">Loading project & metadata…</div>
        
        <!-- Show progress bar while conversion is in progress -->
        <div v-else-if="conversionInProgress" class="conversion-progress">
          <p class="conversion-progress__title">Converting video to frames…</p>
          <div class="conversion-progress__info">
            <span>{{ conversionSaved }} / {{ conversionTotal }} frames</span>
            <span class="conversion-progress__percent">{{ conversionPercent }}%</span>
          </div>
          <div class="conversion-progress__bar">
            <div class="conversion-progress__fill" :style="{ width: `${conversionPercent}%` }"></div>
          </div>
        </div>
        
        <div v-else>
          <div class="preview-wrap">
            <div class="preview">
              <div class="preview__label">Start Preview</div>
              <img :src="previewStartUrl" alt="Start preview" />
            </div>
            <div class="preview">
              <div class="preview__label">End Preview</div>
              <img :src="previewEndUrl" alt="End preview" />
            </div>
          </div>

          <div v-if="duration > 0" class="controls">
            <div class="time-labels">
              <span>Start: <strong>{{ formatTime(startSec) }}</strong></span>
              <span>End: <strong>{{ formatTime(endSec) }}</strong></span>
            </div>
            <DualRangeSlider
              :min="0"
              :max="duration"
              :step="0.1"
              :start-value="startSec"
              :end-value="endSec"
              @update:start-value="startSec = $event"
              @update:end-value="endSec = $event"
              @change="saveTrim"
            />

            <p class="hint" v-if="validationError">{{ validationError }}</p>

            <div class="actions">
              <button 
                class="primary large" 
                @click="startManualLabeling"
                :disabled="!canStartLabeling"
              >
                Start Manual Labeling
              </button>
            </div>
          </div>
          <div v-else class="loading">Waiting for video metadata…</div>
        </div>
      </div>

      <aside class="trim-sidebar">
        <div class="label-settings">
          <div class="label-settings__header">
            <div>
              <h3>Label availability</h3>
              <p class="label-settings__subtitle">
                Enable labels for Manual Labeling and Validation.
              </p>
            </div>
          </div>
          <div v-if="labelSettingsLoading" class="loading">Loading labels…</div>
          <div v-else-if="labelSettings.length === 0" class="label-settings__empty">
            <p>No labels yet.</p>
            <p class="hint-muted">Create labels in the Labels page first.</p>
          </div>
          <div v-else class="label-settings__content">
            <div class="label-tools">
              <input
                v-model="labelSearch"
                class="label-search"
                type="text"
                placeholder="Search labels..."
              />
              <div class="label-filter-row">
                <button
                  v-for="option in filterOptions"
                  :key="option.value"
                  class="filter-chip"
                  :class="{ active: labelFilter === option.value }"
                  type="button"
                  @click="labelFilter = option.value"
                >
                  {{ option.label }}
                </button>
              </div>
              <div class="label-summary">
                <span>{{ enabledCount }} enabled / {{ labelSettings.length }} total</span>
                <span v-if="filteredLabelSettings.length !== labelSettings.length">
                  (showing {{ filteredLabelSettings.length }})
                </span>
              </div>
              <div class="label-bulk-actions">
                <button
                  class="bulk-btn"
                  type="button"
                  :disabled="bulkBusy || filteredLabelSettings.length === 0"
                  @click="applyBulkToVisible(true)"
                >
                  Enable visible
                </button>
                <button
                  class="bulk-btn"
                  type="button"
                  :disabled="bulkBusy || filteredLabelSettings.length === 0"
                  @click="applyBulkToVisible(false)"
                >
                  Disable visible
                </button>
              </div>
            </div>

            <p v-if="patchError" class="label-error">{{ patchError }}</p>
            <div v-if="filteredLabelSettings.length === 0" class="label-settings__empty">
              <p>No matching labels.</p>
              <p class="hint-muted">Try a different search or filter.</p>
            </div>
            <div v-else class="label-grid">
              <article
                v-for="label in filteredLabelSettings"
                :key="label.id"
                class="label-card"
                :class="{ 'is-enabled': label.enabled }"
              >
                <div class="label-card__thumb" :style="{ borderColor: label.color_hex }">
                  <img
                    v-if="label.thumbnail_path && !brokenThumbnailIds[label.id]"
                    :src="thumbnailSrc(label.thumbnail_path)"
                    :alt="`${label.name} thumbnail`"
                    @error="onThumbnailError(label.id)"
                  />
                  <div v-else class="label-card__fallback" :style="{ backgroundColor: `${label.color_hex}22` }">
                    <span :style="{ color: label.color_hex }">{{ label.name.slice(0, 1).toUpperCase() }}</span>
                  </div>
                </div>
                <div class="label-card__body">
                  <div class="label-info">
                    <span class="label-dot" :style="{ backgroundColor: label.color_hex }"></span>
                    <span class="label-name" :title="label.name">{{ label.name }}</span>
                  </div>
                  <label class="toggle" :class="{ disabled: isLabelUpdating(label.id) || bulkBusy }">
                    <input
                      type="checkbox"
                      :checked="label.enabled"
                      :disabled="isLabelUpdating(label.id) || bulkBusy"
                      @change="onLabelToggle(label, $event)"
                    />
                    <span class="toggle-track"></span>
                    <span class="toggle-thumb"></span>
                  </label>
                </div>
              </article>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>

<script lang="ts" setup>
import { onMounted, onUnmounted, ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';
import { API_BASE_URL, resolveApiAssetUrl } from '../lib/api';
import DualRangeSlider from '../components/DualRangeSlider.vue';
import StageNavigation from '../components/StageNavigation.vue';

interface Project {
  id: string;
  name: string;
  active: boolean;
  video_path?: string | null;
  trim_start?: number | null;
  trim_end?: number | null;
  stage: string;
  created_at: string;
  updated_at: string;
  upload_visited: boolean;
  trim_visited: boolean;
  manual_labeling_visited: boolean;
  propagation_visited: boolean;
  validation_visited: boolean;
  export_visited: boolean;
}

interface LabelSetting {
  id: string;
  name: string;
  color_hex: string;
  thumbnail_path: string | null;
  enabled: boolean;
}

type LabelFilter = 'all' | 'enabled' | 'disabled' | 'thumbnail';

const route = useRoute();
const router = useRouter();
const projectId = String(route.params.id ?? '');
const api = axios.create({ baseURL: API_BASE_URL, timeout: 20000 });

const loading = ref(true);
const project = ref<Project | null>(null);
const duration = ref(0);
const startSec = ref(0);
const endSec = ref(0);
const baseApi = API_BASE_URL;
const previewStartUrl = computed(() => `${baseApi}/projects/${projectId}/preview_frame?time_sec=${startSec.value}`);
const previewEndUrl = computed(() => `${baseApi}/projects/${projectId}/preview_frame?time_sec=${endSec.value}`);

// Conversion progress tracking
const conversionSaved = ref(0);
const conversionTotal = ref(0);
const conversionInProgress = ref(false);
let conversionPollInterval: number | null = null;
const labelSettings = ref<LabelSetting[]>([]);
const labelSettingsLoading = ref(false);
const labelSearch = ref('');
const labelFilter = ref<LabelFilter>('all');
const patchError = ref('');
const bulkBusy = ref(false);
const labelPatchInFlight = ref<Record<string, boolean>>({});
const brokenThumbnailIds = ref<Record<string, boolean>>({});
const filterOptions: Array<{ value: LabelFilter; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'enabled', label: 'Enabled' },
  { value: 'disabled', label: 'Disabled' },
  { value: 'thumbnail', label: 'Has thumbnail' },
];

const conversionPercent = computed(() => {
  if (conversionTotal.value === 0) return 0;
  return Math.round((conversionSaved.value / conversionTotal.value) * 100);
});

const enabledCount = computed(() => labelSettings.value.filter(label => label.enabled).length);
const filteredLabelSettings = computed(() => {
  const search = labelSearch.value.trim().toLowerCase();
  return labelSettings.value.filter((label) => {
    if (search && !label.name.toLowerCase().includes(search)) {
      return false;
    }
    if (labelFilter.value === 'enabled' && !label.enabled) {
      return false;
    }
    if (labelFilter.value === 'disabled' && label.enabled) {
      return false;
    }
    if (labelFilter.value === 'thumbnail' && !label.thumbnail_path) {
      return false;
    }
    return true;
  });
});

function formatTime(sec: number): string {
  const s = Math.max(0, sec);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toFixed(1).padStart(4, '0')}`;
}

function validate(): string | '' {
  if (startSec.value < 0) return 'Start must be ≥ 0';
  if (endSec.value <= startSec.value) return 'End must be greater than start';
  if (endSec.value > duration.value) return 'End exceeds video length';
  return '';
}

const validationError = computed(() => validate());

const canStartLabeling = computed(() => {
  // Can start labeling if conversion is complete (not in progress) and no validation errors
  return !conversionInProgress.value && !validationError.value && conversionTotal.value > 0;
});

async function startManualLabeling(): Promise<void> {
  if (!canStartLabeling.value) return;
  
  try {
    // Ensure trim stage is marked as visited first
    const visitResponse = await api.post<Project>(`/projects/${projectId}/mark_stage_visited?stage=trim`);
    if (visitResponse.data) {
      project.value = visitResponse.data;
    }
    
    // Then update stage to manual_labeling
    const patchResponse = await api.patch<Project>(`/projects/${projectId}`, { stage: 'manual_labeling' });
    if (patchResponse.data) {
      project.value = patchResponse.data;
    }
    
    // Navigate to manual labeling page
    router.push({ name: 'ManualLabeling', params: { id: projectId } });
  } catch (error) {
    console.error('Failed to start manual labeling:', error);
  }
}

async function fetchVideoInfo() {
  const { data } = await api.get<{ fps: number; frame_count: number; width: number; height: number; duration: number }>(`/projects/${projectId}/video_info`);
  duration.value = data?.duration ?? 0;
  // Set conversion total to frame count (indicates conversion is complete)
  if (data?.frame_count > 0) {
    conversionTotal.value = data.frame_count;
    conversionInProgress.value = false;
    console.log('[Trim] Frame count from video_info:', data.frame_count);
  }
  // Default end to full duration if not already set
  if (endSec.value === 0 && duration.value > 0) {
    endSec.value = duration.value;
  }
}

async function fetchProject() {
  const { data } = await api.get<Project>(`/projects/${projectId}`);
  project.value = data;
  // Load existing trim values if set
  if (data.trim_start != null) startSec.value = data.trim_start;
  if (data.trim_end != null) endSec.value = data.trim_end;
}

async function saveTrim() {
  const err = validate();
  if (err) return;
  try {
    await api.post<Project>(`/projects/${projectId}/trim`, null, {
      params: { trim_start: startSec.value, trim_end: endSec.value },
    });
  } catch (e) {
    console.error('Failed to save trim', e);
  }
}

async function markStageVisited(): Promise<void> {
  try {
    const { data } = await api.post<Project>(`/projects/${projectId}/mark_stage_visited?stage=trim`);
    // Update local project data with response
    if (data) {
      project.value = data;
    }
  } catch (error) {
    console.error('Failed to mark stage as visited:', error);
  }
}

async function fetchLabelSettings(): Promise<void> {
  labelSettingsLoading.value = true;
  try {
    const { data } = await api.get<LabelSetting[]>(`/projects/${projectId}/label_settings`);
    labelSettings.value = data || [];
    patchError.value = '';
  } catch (error) {
    console.error('Failed to load label settings:', error);
    labelSettings.value = [];
  } finally {
    labelSettingsLoading.value = false;
  }
}

function setLabelUpdating(labelId: string, updating: boolean): void {
  labelPatchInFlight.value = {
    ...labelPatchInFlight.value,
    [labelId]: updating,
  };
}

function isLabelUpdating(labelId: string): boolean {
  return Boolean(labelPatchInFlight.value[labelId]);
}

function thumbnailSrc(path: string): string {
  const base = resolveApiAssetUrl(path);
  const separator = base.includes('?') ? '&' : '?';
  return `${base}${separator}t=${Date.now()}`;
}

function onThumbnailError(labelId: string): void {
  brokenThumbnailIds.value = {
    ...brokenThumbnailIds.value,
    [labelId]: true,
  };
}

async function updateLabelEnabled(label: LabelSetting, nextEnabled: boolean, showError = true): Promise<boolean> {
  if (isLabelUpdating(label.id)) return false;
  const previous = label.enabled;
  label.enabled = nextEnabled;
  setLabelUpdating(label.id, true);
  try {
    const { data } = await api.patch<LabelSetting>(
      `/projects/${projectId}/label_settings/${label.id}`,
      { enabled: nextEnabled },
    );
    if (data) {
      label.enabled = data.enabled;
    }
    return true;
  } catch (error) {
    label.enabled = previous;
    if (showError) {
      patchError.value = 'Failed to update one or more labels. Please try again.';
    }
    console.error('Failed to update label setting:', error);
    return false;
  } finally {
    setLabelUpdating(label.id, false);
  }
}

async function onLabelToggle(label: LabelSetting, event: Event): Promise<void> {
  const target = event.target as HTMLInputElement | null;
  if (!target) return;
  patchError.value = '';
  await updateLabelEnabled(label, target.checked);
}

async function runWithConcurrency<T>(
  items: T[],
  maxConcurrent: number,
  task: (item: T) => Promise<void>,
): Promise<void> {
  const queue = [...items];
  const workers = Array.from({ length: Math.max(1, maxConcurrent) }, async () => {
    while (queue.length > 0) {
      const item = queue.shift();
      if (!item) return;
      await task(item);
    }
  });
  await Promise.all(workers);
}

async function applyBulkToVisible(enabled: boolean): Promise<void> {
  if (bulkBusy.value) return;
  patchError.value = '';
  const candidates = filteredLabelSettings.value.filter(
    (label) => label.enabled !== enabled && !isLabelUpdating(label.id),
  );
  if (candidates.length === 0) return;

  bulkBusy.value = true;
  let failed = 0;
  await runWithConcurrency(candidates, 4, async (label) => {
    const ok = await updateLabelEnabled(label, enabled, false);
    if (!ok) {
      failed += 1;
    }
  });
  bulkBusy.value = false;

  if (failed > 0) {
    patchError.value = `Failed to update ${failed} label${failed === 1 ? '' : 's'}.`;
  }
}

async function checkConversionProgress(): Promise<boolean> {
  try {
    const { data } = await api.get<{ saved: number; total: number; complete: boolean }>(`/projects/${projectId}/conversion/progress`);
    conversionSaved.value = data.saved;
    conversionTotal.value = data.total;
    // Conversion is in progress if not marked complete
    return !data.complete;
  } catch {
    return false;
  }
}

function startConversionPolling() {
  conversionInProgress.value = true;
  console.log('[Trim] Conversion polling started');
  conversionPollInterval = setInterval(async () => {
    const stillInProgress = await checkConversionProgress();
    console.log('[Trim] Polling check:', { 
      saved: conversionSaved.value, 
      total: conversionTotal.value, 
      stillInProgress 
    });
    if (!stillInProgress) {
      console.log('[Trim] Conversion complete, stopping polling');
      stopConversionPolling();
      conversionInProgress.value = false;
    }
  }, 500);
}

function stopConversionPolling() {
  if (conversionPollInterval) {
    clearInterval(conversionPollInterval);
    conversionPollInterval = null;
  }
}

onMounted(async () => {
  try {
    // Ensure both upload and trim are marked as visited
    // (upload might not be visited if project was created with id='new')
    const markUploadRes = await api.post<Project>(`/projects/${projectId}/mark_stage_visited?stage=upload`);
    if (markUploadRes.data) {
      project.value = markUploadRes.data;
    }
    
    // Now mark trim as visited
    await markStageVisited();
    
    // Fetch fresh project data
    await fetchProject();
    
    // Fetch video info FIRST to get duration and frame count
    await fetchVideoInfo();

    // Load project label settings
    await fetchLabelSettings();
    
    // Now check if we need to poll for conversion (only if no frame count found)
    if (conversionTotal.value === 0) {
      console.log('[Trim] No frames found, checking conversion progress...');
      const inProgress = await checkConversionProgress();
      console.log('[Trim] Conversion progress check:', { 
        saved: conversionSaved.value, 
        total: conversionTotal.value, 
        inProgress 
      });
      if (inProgress) {
        console.log('[Trim] Starting conversion polling');
        startConversionPolling();
      }
    } else {
      console.log('[Trim] Found frames, conversion is complete:', { total: conversionTotal.value });
      conversionInProgress.value = false;
    }
  } finally {
    loading.value = false;
  }
});

onUnmounted(() => {
  console.log('[Trim] Unmounting, stopping polling');
  stopConversionPolling();
});
</script>

<style scoped>
.hero {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1rem;
  padding: 1.25rem 1.5rem;
  border: 1px solid var(--border, #dfe3ec);
  background: var(--surface, #ffffff);
  border-radius: 18px;
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.06);
  margin: 1rem 1.25rem 1.25rem;
  width: calc(100% - 2.5rem);
  max-width: 1400px;
}
.hero__text { max-width: 720px; width: 100%; }
.eyebrow { text-transform: uppercase; letter-spacing: 0.08em; font-weight: 700; font-size: 0.8rem; color: var(--muted, #5b6474); margin: 0 0 0.35rem; }
h1 { margin: 0 0 0.25rem; font-size: 2rem; letter-spacing: -0.02em; }
.lede { margin: 0 0 0.75rem; color: var(--muted, #4b5563); line-height: 1.6; }

.content { width: calc(100% - 2.5rem); max-width: 2100px; margin: 0 1.25rem 1.5rem; display: flex; flex-direction: column; gap: 1rem; }
.trim-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 26vw);
  gap: 1rem;
  align-items: start;
}
.trim-card { width: 100%; border: 1px solid var(--border, #dfe3ec); border-radius: 16px; padding: 1.5rem; background: var(--surface, #ffffff); box-shadow: 0 10px 30px rgba(0,0,0,0.05); }
.trim-sidebar { position: sticky; top: 1rem; }
.preview-wrap { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 0.75rem; margin-bottom: 1rem; }
.preview { background: var(--surface-elevated, var(--surface, #ffffff)); border: 1px solid var(--border, #dfe3ec); border-radius: 12px; overflow: hidden; display: flex; flex-direction: column; }
.preview__label { color: var(--text, #0f172a); font-weight: 700; padding: 0.5rem 0.75rem; background: var(--surface, #ffffff); border-bottom: 1px solid var(--border, #dfe3ec); }
.preview img { width: 100%; height: auto; display: block; background: var(--muted, #6b7280); }
.controls { display: flex; flex-direction: column; gap: 1rem; }
.time-labels { display: flex; justify-content: space-between; color: var(--text, #0f172a); font-size: 0.95rem; }
.time-labels strong { font-weight: 700; }
.actions { display: flex; gap: 0.75rem; margin-top: 0.5rem; }
.primary { background: var(--accent, #2563eb); color: white; border: none; padding: 0.6rem 1rem; border-radius: 12px; cursor: pointer; font-weight: 600; }
.primary.large { width: 100%; padding: 1rem 1.5rem; font-size: 1.1rem; }
.primary:disabled { opacity: 0.6; cursor: not-allowed; }
.ghost { background: var(--surface, #ffffff); border: 1px solid var(--border, #dfe3ec); color: var(--text, #0f172a); padding: 0.55rem 0.9rem; border-radius: 12px; font-weight: 600; cursor: pointer; }
.loading { color: var(--muted, #6b7280); }
.hint { color: #b91c1c; }

.label-settings {
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 16px;
  padding: 1.25rem;
  background: var(--surface, #ffffff);
  box-shadow: 0 10px 30px rgba(0,0,0,0.05);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-width: 340px;
}

.label-settings__header h3 {
  margin: 0 0 0.25rem;
  font-size: 1.05rem;
}

.label-settings__subtitle {
  margin: 0;
  color: var(--muted, #4b5563);
  font-size: 0.9rem;
}

.label-settings__content {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.label-tools {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.label-search {
  width: 100%;
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 10px;
  padding: 0.45rem 0.6rem;
  font-size: 0.9rem;
}

.label-filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.filter-chip {
  border: 1px solid var(--border, #dfe3ec);
  background: var(--surface, #fff);
  color: var(--text, #0f172a);
  border-radius: 999px;
  padding: 0.2rem 0.6rem;
  font-size: 0.78rem;
  cursor: pointer;
}

.filter-chip.active {
  border-color: #2563eb;
  color: #2563eb;
  background: rgba(37, 99, 235, 0.08);
}

.label-summary {
  color: var(--muted, #4b5563);
  font-size: 0.82rem;
}

.label-bulk-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.bulk-btn {
  border: 1px solid var(--border, #dfe3ec);
  background: var(--surface, #fff);
  color: var(--text, #0f172a);
  border-radius: 10px;
  padding: 0.35rem 0.55rem;
  font-size: 0.78rem;
  cursor: pointer;
}

.bulk-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.label-error {
  color: #b91c1c;
  margin: 0;
  font-size: 0.82rem;
}

.label-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.65rem;
  max-height: min(58vh, 620px);
  overflow: auto;
  padding-right: 0.25rem;
}

.label-card {
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 12px;
  background: var(--surface-elevated, var(--surface, #ffffff));
  padding: 0.55rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.label-card.is-enabled {
  border-color: rgba(37, 99, 235, 0.5);
  box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.15) inset;
}

.label-card__thumb {
  width: 100%;
  aspect-ratio: 4 / 3;
  border: 2px solid transparent;
  border-radius: 10px;
  overflow: hidden;
  background: var(--surface-muted, #eef2f7);
}

.label-card__thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.label-card__fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
  font-weight: 700;
}

.label-card__body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.35rem;
}

.label-info {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-weight: 550;
  color: var(--text, #0f172a);
  min-width: 0;
}

.label-name {
  display: inline-block;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 0.84rem;
}

.label-dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  border: 1px solid rgba(0, 0, 0, 0.15);
}

.toggle {
  position: relative;
  width: 44px;
  height: 24px;
  flex-shrink: 0;
}

.toggle.disabled {
  opacity: 0.6;
  pointer-events: none;
}

.toggle input {
  opacity: 0;
  width: 0;
  height: 0;
  position: absolute;
}

.toggle-track {
  position: absolute;
  inset: 0;
  border-radius: 999px;
  background: var(--surface-muted, #e5e7eb);
  transition: background 0.2s ease;
}

.toggle-thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: #ffffff;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
  transition: transform 0.2s ease;
}

.toggle input:checked ~ .toggle-track {
  background: #2563eb;
}

.toggle input:checked ~ .toggle-thumb {
  transform: translateX(20px);
}

@media (max-width: 980px) {
  .trim-layout {
    grid-template-columns: minmax(0, 1fr);
  }
  .trim-sidebar {
    position: static;
  }
  .label-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    max-height: none;
  }
  .label-settings {
    min-width: 0;
  }
}

.hint-muted {
  color: var(--muted, #6b7280);
  font-size: 0.85rem;
  margin: 0;
}

@media (max-width: 680px) {
  .label-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 420px) {
  .label-grid {
    grid-template-columns: 1fr;
  }
}

/* Conversion progress styles */
.conversion-progress {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 2rem;
  text-align: center;
}

.conversion-progress__title {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text, #0f172a);
  margin: 0;
}

.conversion-progress__info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--muted, #4b5563);
  font-size: 0.9rem;
}

.conversion-progress__percent {
  font-weight: 700;
  color: #2563eb;
}

.conversion-progress__bar {
  width: 100%;
  height: 12px;
  background: var(--surface-muted, #eef2f7);
  border-radius: 8px;
  overflow: hidden;
}

.conversion-progress__fill {
  height: 100%;
  background: linear-gradient(90deg, #2563eb, #7c3aed);
  border-radius: 8px;
  transition: width 0.3s ease;
}
</style>
