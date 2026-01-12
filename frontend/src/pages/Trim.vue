<template>
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
        Select the start and end positions. The previews update to show the chosen start and end frames. Click "Save Trim" to proceed to labeling.
      </p>
    </div>
  </section>

  <section class="content">
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
            <button class="primary large" disabled>Start Manual Labeling</button>
          </div>
        </div>
        <div v-else class="loading">Waiting for video metadata…</div>
      </div>
    </div>
  </section>
</template>

<script lang="ts" setup>
import { onMounted, onUnmounted, ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';
import DualRangeSlider from '../components/DualRangeSlider.vue';

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
}

const route = useRoute();
const router = useRouter();
const projectId = String(route.params.id ?? '');
const api = axios.create({ baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1', timeout: 20000 });

const loading = ref(true);
const project = ref<Project | null>(null);
const duration = ref(0);
const startSec = ref(0);
const endSec = ref(0);
const baseApi = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1';
const previewStartUrl = computed(() => `${baseApi}/projects/${projectId}/preview_frame?time_sec=${startSec.value}`);
const previewEndUrl = computed(() => `${baseApi}/projects/${projectId}/preview_frame?time_sec=${endSec.value}`);

// Conversion progress tracking
const conversionSaved = ref(0);
const conversionTotal = ref(0);
const conversionInProgress = ref(false);
let conversionPollInterval: ReturnType<typeof setInterval> | null = null;

const conversionPercent = computed(() => {
  if (conversionTotal.value === 0) return 0;
  return Math.round((conversionSaved.value / conversionTotal.value) * 100);
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

async function fetchVideoInfo() {
  const { data } = await api.get<{ fps: number; frame_count: number; width: number; height: number; duration: number }>(`/projects/${projectId}/video_info`);
  duration.value = data?.duration ?? 0;
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
    await fetchProject();
    await fetchVideoInfo();
    
    // Check if conversion is still in progress
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
  margin-bottom: 1.25rem;
  width: 100%;
}
.hero__text { max-width: 720px; width: 100%; }
.eyebrow { text-transform: uppercase; letter-spacing: 0.08em; font-weight: 700; font-size: 0.8rem; color: var(--muted, #5b6474); margin: 0 0 0.35rem; }
h1 { margin: 0 0 0.25rem; font-size: 2rem; letter-spacing: -0.02em; }
.lede { margin: 0 0 0.75rem; color: var(--muted, #4b5563); line-height: 1.6; }

.content { width: 100%; display: flex; flex-direction: column; gap: 1rem; }
.trim-card { width: 100%; border: 1px solid var(--border, #dfe3ec); border-radius: 16px; padding: 1.5rem; background: var(--surface, #ffffff); box-shadow: 0 10px 30px rgba(0,0,0,0.05); }
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
