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
        Select the start and end positions to trim your uploaded video. Use the dual slider to preview the selected range.
      </p>
    </div>
  </section>

  <section class="content">
    <div class="trim-card">
      <div v-if="loading" class="loading">Loading project & video…</div>
      <div v-else>
        <div class="video-wrap">
          <video ref="videoRef" :src="videoUrl" controls @loadedmetadata="onLoadedMetadata" />
        </div>

        <div v-if="duration > 0" class="controls">
          <div class="slider-row">
            <label>Start: <strong>{{ formatTime(startSec) }}</strong></label>
            <input type="range" :min="0" :max="duration" step="0.1" v-model.number="startSec" @input="syncVideoToStart" />
          </div>
          <div class="slider-row">
            <label>End: <strong>{{ formatTime(endSec) }}</strong></label>
            <input type="range" :min="0" :max="duration" step="0.1" v-model.number="endSec" @input="syncVideoToEnd" />
          </div>

          <p class="hint" v-if="validationError">{{ validationError }}</p>

          <div class="actions">
            <button class="primary" :disabled="!!validationError || saving" @click="saveTrim">Save Trim</button>
            <button class="ghost" :disabled="saving" @click="playSelected">Play Selected Range</button>
          </div>
        </div>
        <div v-else class="loading">Waiting for video metadata…</div>
      </div>
    </div>
  </section>
</template>

<script lang="ts" setup>
import { onMounted, ref, computed } from 'vue';
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
const videoRef = ref<HTMLVideoElement | null>(null);
const duration = ref(0);
const startSec = ref(0);
const endSec = ref(0);

const videoUrl = computed(() => `/api/v1/projects/${projectId}/video`);

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

function syncVideoToStart() {
  if (videoRef.value) {
    videoRef.value.currentTime = Math.min(Math.max(startSec.value, 0), duration.value);
  }
}
function syncVideoToEnd() {
  if (videoRef.value) {
    videoRef.value.currentTime = Math.min(Math.max(endSec.value, 0), duration.value);
  }
}

function playSelected() {
  const v = videoRef.value;
  if (!v) return;
  v.currentTime = startSec.value;
  v.play();
  const tick = () => {
    if (v.currentTime >= endSec.value || v.paused) {
      v.pause();
      v.currentTime = endSec.value;
      return;
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

async function onLoadedMetadata() {
  const v = videoRef.value;
  if (!v) return;
  duration.value = v.duration;
  // Initialize sliders using existing trim or full duration
  startSec.value = project.value?.trim_start ?? 0;
  endSec.value = project.value?.trim_end ?? duration.value;
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
  } finally {
    loading.value = false;
  }
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
.video-wrap { display: flex; justify-content: center; background: #0b1020; border-radius: 12px; overflow: hidden; margin-bottom: 1rem; }
video { width: 100%; max-height: 360px; }
.controls { display: flex; flex-direction: column; gap: 0.75rem; }
.slider-row { display: grid; grid-template-columns: 180px 1fr; align-items: center; gap: 0.75rem; }
.actions { display: flex; gap: 0.75rem; }
.primary { background: var(--accent, #2563eb); color: white; border: none; padding: 0.6rem 1rem; border-radius: 12px; cursor: pointer; font-weight: 600; }
.primary:disabled { opacity: 0.6; cursor: not-allowed; }
.ghost { background: var(--surface, #ffffff); border: 1px solid var(--border, #dfe3ec); color: var(--text, #0f172a); padding: 0.55rem 0.9rem; border-radius: 12px; font-weight: 600; cursor: pointer; }
.loading { color: var(--muted, #6b7280); }
.hint { color: #b91c1c; }
</style>
