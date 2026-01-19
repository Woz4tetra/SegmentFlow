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
      <p class="eyebrow">Stage: Export</p>
      <h1>{{ project?.name ?? 'Loading...' }}</h1>
      <p class="lede">
        Download output JPEGs and YOLO label files. Labels use the largest contour for each class.
      </p>
    </div>
  </section>

  <section class="content">
    <div class="export-card">
      <div v-if="loading" class="loading">Loading project…</div>
      <div v-else class="export-body">
        <div class="export-info">
          <h3>YOLO Export</h3>
          <p>Includes images and labels in a ZIP with a classes.txt file.</p>
        </div>
        <button class="primary large" type="button" :disabled="downloading" @click="downloadExport">
          {{ downloading ? 'Preparing...' : 'Download Export ZIP' }}
        </button>
        <p v-if="error" class="error">{{ error }}</p>
      </div>
    </div>
  </section>
</template>

<script lang="ts" setup>
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import axios from 'axios';
import { API_BASE_URL, buildApiUrl } from '../lib/api';
import StageNavigation from '../components/StageNavigation.vue';

interface Project {
  id: string;
  name: string;
  stage: string;
  upload_visited: boolean;
  trim_visited: boolean;
  manual_labeling_visited: boolean;
  propagation_visited: boolean;
  validation_visited: boolean;
  export_visited: boolean;
}

const route = useRoute();
const projectId = String(route.params.id ?? '');
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20000,
});

const loading = ref(true);
const downloading = ref(false);
const error = ref('');
const project = ref<Project | null>(null);

async function fetchProject(): Promise<void> {
  const { data } = await api.get<Project>(`/projects/${projectId}`);
  project.value = data;
}

async function markVisited(): Promise<void> {
  const { data } = await api.post<Project>(`/projects/${projectId}/mark_stage_visited?stage=export`);
  if (data) {
    project.value = data;
  }
  if (project.value?.stage !== 'export') {
    const stageRes = await api.patch<Project>(`/projects/${projectId}`, { stage: 'export' });
    if (stageRes.data) {
      project.value = stageRes.data;
    }
  }
}

async function downloadExport(): Promise<void> {
  if (downloading.value) return;
  downloading.value = true;
  error.value = '';
  try {
    const url = buildApiUrl(`/projects/${projectId}/export/yolo`);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', '');
    link.setAttribute('rel', 'noopener');
    link.setAttribute('target', '_blank');
    document.body.appendChild(link);
    link.click();
    link.remove();
  } catch (err) {
    error.value = 'Failed to download export. Please try again.';
  } finally {
    downloading.value = false;
  }
}

onMounted(async () => {
  loading.value = true;
  try {
    await fetchProject();
    await markVisited();
  } catch (err) {
    error.value = 'Failed to load export data.';
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
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.06), rgba(99, 102, 241, 0.04)),
    var(--surface, #ffffff);
  border-radius: 18px;
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.06);
  margin: 1rem 1.25rem 0;
  width: calc(100% - 2.5rem);
  max-width: 1400px;
}

.hero__text {
  max-width: 800px;
}

.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 700;
  font-size: 0.8rem;
  color: var(--muted, #5b6474);
  margin: 0 0 0.35rem;
}

.lede {
  margin: 0;
  color: var(--muted, #4b5563);
  line-height: 1.6;
  font-size: 0.95rem;
}

.content {
  width: 100%;
  display: flex;
  justify-content: center;
  padding: 1.5rem 1.25rem;
}

.export-card {
  width: 100%;
  max-width: 720px;
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 18px;
  padding: 2rem;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.05);
}

.export-body {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.export-info h3 {
  margin: 0 0 0.3rem;
  font-size: 1rem;
}

.export-info p {
  margin: 0;
  color: var(--muted, #6b7280);
}

.primary.large {
  padding: 0.9rem 1.6rem;
  border-radius: 12px;
  border: none;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: #ffffff;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.primary.large:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.35);
}

.primary.large:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ghost {
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #dfe3ec);
  padding: 0.65rem 1rem;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  text-decoration: none;
  color: var(--text, #0f172a);
  font-size: 0.9rem;
  font-weight: 600;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.ghost:hover {
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: white;
  border-color: transparent;
  box-shadow: 0 6px 20px rgba(37, 99, 235, 0.25);
  transform: translateY(-2px);
}

.icon {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
}

.loading {
  color: var(--muted, #6b7280);
}

.error {
  color: #dc2626;
  font-weight: 600;
}
</style>
