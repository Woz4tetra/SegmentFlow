<template>
  <div class="propagation-page">
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
        <p class="eyebrow">Stage: Label Propagation</p>
        <h1>{{ project?.name ?? 'Loading...' }}</h1>
        <p class="lede">
          Automatically propagate labels from manually labeled frames to the rest of the video.
        </p>
      </div>
    </section>

    <div v-if="loading" class="loading-container">
      <div class="loading-spinner"></div>
      <p>Loading project...</p>
    </div>

    <div v-else class="content-wrapper">
      <div class="propagation-container">
        <!-- Status Card -->
        <div class="status-card" :class="statusClass">
          <div class="status-icon">
            <svg v-if="jobStatus === 'completed'" viewBox="0 0 24 24" width="48" height="48">
              <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" />
              <path d="M8 12l3 3 5-6" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <svg v-else-if="jobStatus === 'failed'" viewBox="0 0 24 24" width="48" height="48">
              <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" />
              <path d="M15 9l-6 6M9 9l6 6" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" />
            </svg>
            <svg v-else-if="jobStatus === 'running'" viewBox="0 0 24 24" width="48" height="48" class="spinning">
              <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="45 20" />
            </svg>
            <svg v-else viewBox="0 0 24 24" width="48" height="48">
              <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" />
              <path d="M12 8v4l3 3" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" />
            </svg>
          </div>
          <h2 class="status-title">{{ statusTitle }}</h2>
          <p class="status-message">{{ statusMessage }}</p>
        </div>

        <!-- Progress Section -->
        <div v-if="progress || jobStatus === 'running'" class="progress-section">
          <div class="progress-header">
            <span class="progress-label">Overall Progress</span>
            <span class="progress-percentage">{{ Math.round(progress?.progress_percent ?? 0) }}%</span>
          </div>
          <div class="progress-bar-container">
            <div 
              class="progress-bar-fill" 
              :style="{ width: `${progress?.progress_percent ?? 0}%` }"
              :class="{ complete: jobStatus === 'completed' }"
            ></div>
          </div>
          <div class="progress-details">
            <div class="detail-item">
              <span class="detail-label">Segment</span>
              <span class="detail-value">{{ progress?.current_segment ?? 0 }} / {{ progress?.total_segments ?? 0 }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Frames Completed</span>
              <span class="detail-value">{{ progress?.frames_completed ?? 0 }} / {{ progress?.total_frames ?? 0 }}</span>
            </div>
            <div class="detail-item" v-if="progress?.estimated_remaining_ms && progress.estimated_remaining_ms > 0">
              <span class="detail-label">Estimated Remaining</span>
              <span class="detail-value">{{ formatTime(progress.estimated_remaining_ms) }}</span>
            </div>
          </div>
        </div>

        <!-- Stats Section -->
        <div v-if="stats" class="stats-section">
          <h3>Propagation Statistics</h3>
          <div class="stats-grid">
            <div class="stat-card">
              <span class="stat-value">{{ stats.manualFrames }}</span>
              <span class="stat-label">Manually Labeled</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ stats.propagatedFrames }}</span>
              <span class="stat-label">Propagated</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ stats.totalFrames }}</span>
              <span class="stat-label">Total Frames</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ stats.labels }}</span>
              <span class="stat-label">Labels</span>
            </div>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="actions-section">
          <button 
            v-if="!jobId && !jobStatus"
            @click="startPropagation"
            class="btn-primary btn-large"
            :disabled="starting"
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="5,3 19,12 5,21" />
            </svg>
            {{ starting ? 'Starting...' : 'Start Propagation' }}
          </button>

          <button 
            v-if="jobStatus === 'completed'"
            @click="goToValidation"
            class="btn-primary btn-large"
          >
            <img
              src="/check_circle_256dp_FFFFFF_FILL0_wght400_GRAD0_opsz48.svg"
              alt=""
              class="btn-icon"
            />
            Continue to Validation
          </button>

          <button 
            v-if="jobStatus === 'failed'"
            @click="retryPropagation"
            class="btn-secondary btn-large"
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 12a9 9 0 019-9 9.75 9.75 0 016.74 2.74L21 8" />
              <path d="M21 3v5h-5" />
              <path d="M21 12a9 9 0 01-9 9 9.75 9.75 0 01-6.74-2.74L3 16" />
              <path d="M8 16H3v5" />
            </svg>
            Retry Propagation
          </button>

          <router-link 
            :to="{ name: 'ManualLabeling', params: { id: projectId } }"
            class="btn-ghost"
          >
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M15 19l-7-7 7-7" />
            </svg>
            Back to Manual Labeling
          </router-link>
        </div>
      </div>
    </div>

    <!-- Notification Toast -->
    <Transition name="toast">
      <div v-if="showNotification" class="notification-toast" :class="notificationType">
        <div class="notification-icon">
          <svg v-if="notificationType === 'success'" viewBox="0 0 24 24" width="24" height="24">
            <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" />
            <path d="M8 12l3 3 5-6" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" />
          </svg>
          <svg v-else viewBox="0 0 24 24" width="24" height="24">
            <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" />
            <path d="M12 8v4M12 16h.01" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" />
          </svg>
        </div>
        <div class="notification-content">
          <strong>{{ notificationTitle }}</strong>
          <p>{{ notificationMessage }}</p>
        </div>
        <button @click="showNotification = false" class="notification-close">×</button>
      </div>
    </Transition>
  </div>
</template>

<script lang="ts" setup>
import { onMounted, onUnmounted, ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';
import { API_BASE_URL, buildWebSocketUrl } from '../lib/api';
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

interface PropagationProgress {
  job_id: string;
  project_id: string;
  status: string;
  current_segment: number;
  total_segments: number;
  current_frame: number;
  frames_completed: number;
  total_frames: number;
  progress_percent: number;
  estimated_remaining_ms: number;
  error: string | null;
}

interface FrameStatusSummary {
  manual_frames: number;
  propagated_frames: number;
  total_frames: number;
  labels_count: number;
}

interface PropagationStats {
  manualFrames: number;
  propagatedFrames: number;
  totalFrames: number;
  labels: number;
}

interface PropagationStatusResponse {
  job_id: string;
  project_id: string;
  status: string;
  progress: PropagationProgress | null;
  started_at: string | null;
  completed_at: string | null;
}

const route = useRoute();
const router = useRouter();
const projectId = String(route.params.id ?? '');
const api = axios.create({ 
  baseURL: API_BASE_URL, 
  timeout: 30000 
});

const loading = ref(true);
const project = ref<Project | null>(null);
const jobId = ref<string | null>(null);
const jobStatus = ref<string | null>(null);
const progress = ref<PropagationProgress | null>(null);
const stats = ref<PropagationStats | null>(null);
const starting = ref(false);

const jobStorageKey = `segmentflow:propagationJob:${projectId}`;

// Notification state
const showNotification = ref(false);
const notificationType = ref<'success' | 'error'>('success');
const notificationTitle = ref('');
const notificationMessage = ref('');

// WebSocket connection
let websocket: WebSocket | null = null;

const statusClass = computed(() => {
  switch (jobStatus.value) {
    case 'completed': return 'status-success';
    case 'failed': return 'status-error';
    case 'running': return 'status-running';
    default: return 'status-idle';
  }
});

const statusTitle = computed(() => {
  switch (jobStatus.value) {
    case 'completed': return 'Propagation Complete!';
    case 'failed': return 'Propagation Failed';
    case 'running': return 'Propagating Labels...';
    case 'queued': return 'Starting Propagation...';
    default: return 'Ready to Propagate';
  }
});

const statusMessage = computed(() => {
  switch (jobStatus.value) {
    case 'completed': 
      return 'Labels have been successfully propagated to all frames. You can now review and validate the results.';
    case 'failed': 
      return progress.value?.error ?? 'An error occurred during propagation. Please try again.';
    case 'running': 
      return 'Please wait while labels are being propagated across the video frames.';
    case 'queued': 
      return 'The propagation job is being prepared...';
    default: 
      return 'Click "Start Propagation" to automatically label all frames based on your manual labels.';
  }
});

function formatTime(ms: number): string {
  const seconds = Math.ceil(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds}s`;
}

async function fetchProject(): Promise<void> {
  try {
    const { data } = await api.get<Project>(`/projects/${projectId}`);
    project.value = data;
  } catch (error) {
    console.error('Failed to fetch project:', error);
  }
}

async function fetchStats(): Promise<void> {
  try {
    const { data } = await api.get<{ summary: FrameStatusSummary }>(
      `/projects/${projectId}/frame-statuses`,
    );
    const summary = data.summary || {};
    stats.value = {
      manualFrames: summary.manual_frames ?? 0,
      propagatedFrames: summary.propagated_frames ?? 0,
      totalFrames: summary.total_frames ?? 0,
      labels: summary.labels_count ?? 0,
    };
  } catch (error) {
    console.error('Failed to fetch stats:', error);
  }
}

async function startPropagation(): Promise<void> {
  if (starting.value) return;
  starting.value = true;
  
  try {
    const { data } = await api.post(`/projects/${projectId}/propagate`, {
      project_id: projectId,
    });
    
    jobId.value = data.job_id;
    jobStatus.value = data.status;
    sessionStorage.setItem(jobStorageKey, data.job_id);
    
    // Connect to WebSocket for progress updates
    connectWebSocket(data.job_id);
    
  } catch (error: any) {
    console.error('Failed to start propagation:', error);
    showErrorNotification(
      'Failed to Start',
      error.response?.data?.detail ?? 'Could not start propagation. Please try again.'
    );
  } finally {
    starting.value = false;
  }
}

async function restorePropagationJob(): Promise<void> {
  const storedJobId = sessionStorage.getItem(jobStorageKey);
  if (!storedJobId) return;

  try {
    const { data } = await api.get<PropagationStatusResponse>(
      `/projects/${projectId}/propagate/${storedJobId}`,
    );
    jobId.value = data.job_id;
    jobStatus.value = data.status;
    progress.value = data.progress ?? null;

    if (data.status === 'running' || data.status === 'queued') {
      connectWebSocket(data.job_id);
    }
  } catch (error) {
    console.warn('Stored propagation job not found, clearing cache.', error);
    sessionStorage.removeItem(jobStorageKey);
    jobId.value = null;
    jobStatus.value = null;
    progress.value = null;
  }
}

function connectWebSocket(jobIdValue: string): void {
  const wsUrl = buildWebSocketUrl(`/projects/${projectId}/propagate/${jobIdValue}/ws`);
  console.log('Connecting to propagation WebSocket:', wsUrl);
  
  websocket = new WebSocket(wsUrl);
  
  websocket.onopen = () => {
    console.log('Propagation WebSocket connected');
  };
  
  websocket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      
      // Ignore ping messages
      if (data.type === 'ping') return;
      
      // Update progress
      progress.value = data as PropagationProgress;
      jobStatus.value = data.status;
      
      // Show notification on completion
      if (data.status === 'completed') {
        showSuccessNotification(
          'Propagation Complete!',
          'Labels have been successfully propagated to all frames.'
        );
        fetchStats(); // Refresh stats
      } else if (data.status === 'failed') {
        showErrorNotification(
          'Propagation Failed',
          data.error ?? 'An error occurred during propagation.'
        );
      }
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  };
  
  websocket.onerror = (error) => {
    console.error('Propagation WebSocket error:', error);
  };
  
  websocket.onclose = () => {
    console.log('Propagation WebSocket closed');
  };
}

function showSuccessNotification(title: string, message: string): void {
  notificationType.value = 'success';
  notificationTitle.value = title;
  notificationMessage.value = message;
  showNotification.value = true;
  
  // Auto-hide after 5 seconds
  setTimeout(() => {
    showNotification.value = false;
  }, 5000);
}

function showErrorNotification(title: string, message: string): void {
  notificationType.value = 'error';
  notificationTitle.value = title;
  notificationMessage.value = message;
  showNotification.value = true;
  
  // Auto-hide after 8 seconds for errors
  setTimeout(() => {
    showNotification.value = false;
  }, 8000);
}

function goToValidation(): void {
  router.push({ name: 'Validation', params: { id: projectId } });
}

function retryPropagation(): void {
  sessionStorage.removeItem(jobStorageKey);
  jobId.value = null;
  jobStatus.value = null;
  progress.value = null;
  startPropagation();
}

async function markStageVisited(): Promise<void> {
  try {
    const { data } = await api.post<Project>(`/projects/${projectId}/mark_stage_visited?stage=propagation`);
    if (data) {
      project.value = data;
    }
  } catch (error) {
    console.error('Failed to mark stage as visited:', error);
  }
}

onMounted(async () => {
  loading.value = true;
  
  try {
    await fetchProject();
    await fetchStats();
    await markStageVisited();
    await restorePropagationJob();
  } catch (error) {
    console.error('Failed during initialization:', error);
  }
  
  loading.value = false;
});

onUnmounted(() => {
  if (websocket) {
    websocket.close();
    websocket = null;
  }
});
</script>

<style scoped>
.propagation-page {
  min-height: 100vh;
  background: var(--bg, #f5f7fb);
}

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

h1 {
  margin: 0 0 0.25rem;
  font-size: 2rem;
  letter-spacing: -0.02em;
  color: var(--text, #0f172a);
}

.lede {
  margin: 0;
  color: var(--muted, #4b5563);
  line-height: 1.6;
  font-size: 0.95rem;
}

.loading-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 4rem;
  color: var(--muted, #4b5563);
  gap: 1rem;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border, #dfe3ec);
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.content-wrapper {
  width: 100%;
  display: flex;
  justify-content: center;
  padding: 1.5rem 1.25rem;
}

.propagation-container {
  width: 100%;
  max-width: 800px;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.status-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 2.5rem 2rem;
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 20px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
}

.status-card.status-success {
  border-color: #22c55e;
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.05), rgba(34, 197, 94, 0.02));
}

.status-card.status-success .status-icon {
  color: #22c55e;
}

.status-card.status-error {
  border-color: #ef4444;
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.05), rgba(239, 68, 68, 0.02));
}

.status-card.status-error .status-icon {
  color: #ef4444;
}

.status-card.status-running {
  border-color: #2563eb;
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.05), rgba(37, 99, 235, 0.02));
}

.status-card.status-running .status-icon {
  color: #2563eb;
}

.status-icon {
  margin-bottom: 1rem;
  color: var(--muted, #6b7280);
}

.status-icon .spinning {
  animation: spin 1.5s linear infinite;
}

.status-title {
  margin: 0 0 0.5rem;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text, #0f172a);
}

.status-message {
  margin: 0;
  color: var(--muted, #6b7280);
  line-height: 1.6;
  max-width: 500px;
}

.progress-section {
  padding: 1.5rem;
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 16px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.progress-label {
  font-weight: 600;
  color: var(--text, #0f172a);
}

.progress-percentage {
  font-size: 1.25rem;
  font-weight: 700;
  color: #2563eb;
}

.progress-bar-container {
  height: 12px;
  background: var(--surface-muted, #f3f4f6);
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 1rem;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #2563eb, #7c3aed);
  border-radius: 6px;
  transition: width 0.3s ease;
}

.progress-bar-fill.complete {
  background: linear-gradient(90deg, #22c55e, #16a34a);
}

.progress-details {
  display: flex;
  gap: 2rem;
  flex-wrap: wrap;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.detail-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted, #9ca3af);
  font-weight: 600;
}

.detail-value {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text, #0f172a);
}

.stats-section {
  padding: 1.5rem;
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 16px;
}

.stats-section h3 {
  margin: 0 0 1rem;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted, #6b7280);
  font-weight: 700;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1rem;
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 1rem;
  background: var(--surface-muted, #f9fafb);
  border-radius: 12px;
  text-align: center;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--text, #0f172a);
}

.stat-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted, #9ca3af);
  font-weight: 600;
  margin-top: 0.25rem;
}

.actions-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding-top: 1rem;
}

.btn-primary {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 1rem 2rem;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: white;
  border: none;
  border-radius: 14px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 4px 16px rgba(37, 99, 235, 0.25);
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.35);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary svg {
  fill: currentColor;
  stroke: none;
}

.btn-primary .btn-icon {
  width: 20px;
  height: 20px;
  display: inline-block;
}

.btn-secondary {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 1rem 2rem;
  background: var(--surface, #ffffff);
  color: var(--text, #0f172a);
  border: 2px solid var(--border, #dfe3ec);
  border-radius: 14px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-secondary:hover {
  border-color: #2563eb;
  color: #2563eb;
  transform: translateY(-1px);
}

.btn-ghost {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  color: var(--muted, #6b7280);
  font-size: 0.9rem;
  font-weight: 500;
  text-decoration: none;
  transition: color 0.2s ease;
}

.btn-ghost:hover {
  color: #2563eb;
}

.btn-large {
  min-width: 280px;
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

/* Notification Toast */
.notification-toast {
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 1rem 1.25rem;
  background: var(--surface, #ffffff);
  border-radius: 14px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
  z-index: 1000;
  max-width: 400px;
}

.notification-toast.success {
  border-left: 4px solid #22c55e;
}

.notification-toast.success .notification-icon {
  color: #22c55e;
}

.notification-toast.error {
  border-left: 4px solid #ef4444;
}

.notification-toast.error .notification-icon {
  color: #ef4444;
}

.notification-icon {
  flex-shrink: 0;
}

.notification-content {
  flex: 1;
}

.notification-content strong {
  display: block;
  font-size: 0.95rem;
  color: var(--text, #0f172a);
  margin-bottom: 0.25rem;
}

.notification-content p {
  margin: 0;
  font-size: 0.85rem;
  color: var(--muted, #6b7280);
  line-height: 1.5;
}

.notification-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: var(--muted, #9ca3af);
  cursor: pointer;
  padding: 0;
  line-height: 1;
  transition: color 0.2s ease;
}

.notification-close:hover {
  color: var(--text, #0f172a);
}

/* Toast animation */
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(100px);
}

.toast-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
</style>

