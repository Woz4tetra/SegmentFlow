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
        Select the start and end positions. The previews update to show the chosen start and end frames. Click "Convert to Images" to generate JPEGs for the selected range.
      </p>
    </div>
  </section>

  <section class="content">
    <div class="trim-card">
      <div v-if="loading" class="loading">Loading project & metadata…</div>
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
          <div class="slider-row">
            <label>Start: <strong>{{ formatTime(startSec) }}</strong></label>
            <input type="range" :min="0" :max="duration" step="0.1" v-model.number="startSec" />
          </div>
          <div class="slider-row">
            <label>End: <strong>{{ formatTime(endSec) }}</strong></label>
            <input type="range" :min="0" :max="duration" step="0.1" v-model.number="endSec" />
          </div>

          <p class="hint" v-if="validationError">{{ validationError }}</p>

          <div class="actions">
            <button class="primary" :disabled="!!validationError || saving" @click="saveTrim">Save Trim</button>
            <button class="ghost" :disabled="!!validationError || converting" @click="convertImages">Convert to Images</button>
          </div>
        </div>
        <div v-else class="loading">Waiting for video metadata…</div>
      </div>
    </div>
  </section>
</template>

<script lang="ts" setup>
import { onMounted, ref, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';

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
const saving = ref(false);
const project = ref<Project | null>(null);
const converting = ref(false);
const duration = ref(0);
const startSec = ref(0);
const endSec = ref(0);
const baseApi = import.meta.env.VITE_API_URL ?? '/api/v1';
const previewStartUrl = computed(() => `${baseApi}/projects/${projectId}/preview_frame?time_sec=${startSec.value}`);
const previewEndUrl = computed(() => `${baseApi}/projects/${projectId}/preview_frame?time_sec=${endSec.value}`);

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
}

async function fetchProject() {
  const { data } = await api.get<Project>(`/projects/${projectId}`);
  project.value = data;
}

async function saveTrim() {
  const err = validate();
  if (err) return;
  try {
    saving.value = true;
    // For now, persist seconds as integers; future conversion to frames will be added in processing step
    const startInt = Math.floor(startSec.value);
    const endInt = Math.floor(endSec.value);
    const { data } = await api.post<Project>(`/projects/${projectId}/trim`, null, {
      params: { trim_start: startInt, trim_end: endInt },
    });
    project.value = data;
    // Optionally proceed to next stage later; for now remain on Trim
    // router.push({ name: 'ManualLabeling', params: { id: projectId } });
  } catch (e) {
    console.error('Failed to save trim', e);
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  try {
    await fetchProject();
    await fetchVideoInfo();
  } finally {
    loading.value = false;
  }
});

async function convertImages() {
  const err = validate();
  if (err) return;
  try {
    converting.value = true;
    const { data } = await api.post(`/projects/${projectId}/convert_images`, null, {
      params: { trim_start: startSec.value, trim_end: endSec.value },
    });
    console.log('Conversion summary:', data);
  } catch (e) {
    console.error('Failed to convert images', e);
  } finally {
    converting.value = false;
  }
}
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
.preview { background: #0b1020; border-radius: 12px; overflow: hidden; display: flex; flex-direction: column; }
.preview__label { color: #cbd5e1; font-weight: 700; padding: 0.5rem 0.75rem; }
.preview img { width: 100%; height: auto; display: block; }
.controls { display: flex; flex-direction: column; gap: 0.75rem; }
.slider-row { display: grid; grid-template-columns: 180px 1fr; align-items: center; gap: 0.75rem; }
.actions { display: flex; gap: 0.75rem; }
.primary { background: var(--accent, #2563eb); color: white; border: none; padding: 0.6rem 1rem; border-radius: 12px; cursor: pointer; font-weight: 600; }
.primary:disabled { opacity: 0.6; cursor: not-allowed; }
.ghost { background: var(--surface, #ffffff); border: 1px solid var(--border, #dfe3ec); color: var(--text, #0f172a); padding: 0.55rem 0.9rem; border-radius: 12px; font-weight: 600; cursor: pointer; }
.loading { color: var(--muted, #6b7280); }
.hint { color: #b91c1c; }
</style>
