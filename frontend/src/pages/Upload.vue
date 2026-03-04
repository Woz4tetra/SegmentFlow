<template>
  <!-- Stage Navigation -->
  <StageNavigation v-if="project" :project="project" />

  <!-- Top hero: same width and style approach as Home hero -->
  <section class="hero">
    <router-link to="/" class="ghost btn-icon" title="Back to Projects">
      <svg class="icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
        <path d="M15 19l-7-7 7-7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      <span>Back to Projects</span>
    </router-link>
    <div class="hero__text">
      <p class="eyebrow">Create Project</p>
      <h1>Upload Video</h1>
      <p class="lede">
        Select a video file to create a new annotation project. Your project will be named based on the video filename.
      </p>
    </div>
  </section>

  <!-- Main upload card: full-width like Home hero card -->
  <section class="content">
    <div v-if="errorMessage" class="error-banner">
      <img
        src="/error_256dp_000000_FILL0_wght400_GRAD0_opsz48.svg"
        alt="Error icon"
        class="error-banner__icon"
        width="20"
        height="20"
      />
      <span>{{ errorMessage }}</span>
    </div>
    <div class="upload-card">
      <FileUpload
        :disabled="isCreatingProject || isConverting"
        :is-uploading="isCreatingProject || isConverting"
        :upload-progress="uploadProgress"
        :uploading-file-name="uploadMessage"
        @file-selected="handleFileSelect"
      />
    </div>
  </section>
</template>

<script lang="ts" setup>
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useProjectsStore } from '../stores/projects';
import FileUpload from '../components/FileUpload.vue';
import StageNavigation from '../components/StageNavigation.vue';
import axios from 'axios';
import { API_BASE_URL } from '../lib/api';

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

const router = useRouter();
const route = useRoute();
const routeProjectId = route.params.id ? String(route.params.id) : '';
const projectsStore = useProjectsStore();
const project = ref<Project | null>(null);
const isCreatingProject = ref(false);
const isConverting = ref(false);
const uploadProgress = ref(0);
const uploadMessage = ref('');
const errorMessage = ref('');
const conversionProgress = ref({ saved: 0, total: 0 });
let conversionPollInterval: number | null = null;

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

const conversionProgressPercent = computed(() => {
  if (conversionProgress.value.total === 0) return 0;
  return Math.round((conversionProgress.value.saved / conversionProgress.value.total) * 100);
});

async function fetchProject(): Promise<void> {
  if (!routeProjectId) return;
  try {
    const { data } = await api.get<Project>(`/projects/${routeProjectId}`);
    project.value = data;
  } catch (error) {
    console.error('Failed to fetch project:', error);
  }
}

async function markStageVisited(): Promise<void> {
  if (!routeProjectId) return;
  try {
    const { data } = await api.post<Project>(`/projects/${routeProjectId}/mark_stage_visited?stage=upload`);
    // Update local project data with response
    if (data) {
      project.value = data;
    }
  } catch (error) {
    console.error('Failed to mark stage as visited:', error);
  }
}

async function computeFileHash(file: File): Promise<string> {
  console.log('Computing file hash...');
  const buffer = await file.arrayBuffer();

  if (typeof crypto !== 'undefined' && crypto.subtle?.digest) {
    const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    console.log('File hash (SHA-256):', hashHex);
    return hashHex;
  }

  // SubtleCrypto is unavailable in non-secure contexts; skip hash verification.
  console.warn('SubtleCrypto unavailable; skipping file hash verification.');
  return '';
}

// Upload file in chunks to backend
async function uploadVideoFile(projectId: string, file: File): Promise<void> {
  const CHUNK_SIZE = 10 * 1024 * 1024; // 10MB chunks
  const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
  
  console.log(`Uploading file: ${file.name}, size: ${file.size} bytes, chunks: ${totalChunks}`);
  
  // Reset progress
  uploadProgress.value = 0;
  uploadMessage.value = "Uploading video...";
  
  // Compute file hash (1-5% progress)
  console.log('Computing file hash...');
  const fileHash = await computeFileHash(file);
  console.log('File hash:', fileHash);
  uploadProgress.value = 5;
  
  // Initialize upload session (5-10% progress)
  console.log('Initializing upload session...');
  await api.post(`/projects/${projectId}/upload/init`, null, {
    params: {
      total_chunks: totalChunks,
      total_size: file.size,
      file_hash: fileHash,
      original_name: file.name,
    },
  });
  console.log('Upload session initialized');
  uploadProgress.value = 10;
  
  // Upload chunks (10-50% progress)
  for (let i = 0; i < totalChunks; i++) {
    const start = i * CHUNK_SIZE;
    const end = Math.min(start + CHUNK_SIZE, file.size);
    const chunk = file.slice(start, end);
    
    console.log(`Uploading chunk ${i}/${totalChunks - 1}...`);
    
    const formData = new FormData();
    formData.append('chunk_data', chunk);
    
    await api.post(`/projects/${projectId}/upload/chunk`, formData, {
      params: { chunk_number: i },
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    
    // Update progress: 10% to 50% based on chunks uploaded
    const chunkProgress = ((i + 1) / totalChunks) * 40;
    uploadProgress.value = 10 + Math.round(chunkProgress);
    
    console.log(`Chunk ${i} uploaded successfully`);
  }
  
  // Complete upload (50-55% progress)
  uploadProgress.value = 50;
  console.log('Completing upload...');
  await api.post(`/projects/${projectId}/upload/complete`);
  uploadProgress.value = 55;
  console.log('Upload completed successfully! Waiting for image conversion...');
  
  // Poll for conversion progress (55-95% progress)
  isConverting.value = true;
  conversionProgress.value = { saved: 0, total: 0 };
  uploadMessage.value = 'Converting video to images...';
  
  const pollConversion = async () => {
    try {
      const { data } = await api.get(`/projects/${projectId}/conversion/progress`);
      conversionProgress.value = data;
      
      // Check if conversion failed
      if (data.error) {
        if (conversionPollInterval) clearInterval(conversionPollInterval);
        isConverting.value = false;
        errorMessage.value = 'Video upload failed. Please try again with a different video file.';
        return false;
      }
      
      if (data.total > 0) {
        // Map 55-95% to conversion progress
        const conversionPercent = (data.saved / data.total) * 40;
        uploadProgress.value = Math.round(Math.min(55 + conversionPercent, 94));
      }
      
      // Check if conversion is done (saved === total and both > 0)
      if (data.total > 0 && data.saved >= data.total) {
        uploadProgress.value = 95;
        if (conversionPollInterval) clearInterval(conversionPollInterval);
        return true;
      }
      return false;
    } catch (e) {
      console.warn('Could not fetch conversion progress:', e);
      return false;
    }
  };
  
  // Wait for conversion to complete or timeout after 5 minutes
  const timeout = 5 * 60 * 1000; // 5 minutes
  let done = false;

  await new Promise<void>((resolve) => {
    const startTime = Date.now();

    const finish = () => {
      if (conversionPollInterval) {
        clearInterval(conversionPollInterval);
        conversionPollInterval = null;
      }
      resolve();
    };

    const timeoutId = setTimeout(() => {
      console.warn('Image conversion timed out after 5 minutes.');
      finish();
    }, timeout);

    const pollAndCheck = async () => {
      done = await pollConversion();
      if (done) {
        clearTimeout(timeoutId);
        finish();
      } else if (Date.now() - startTime >= timeout) {
        // Safety check in case timeout fires slightly later
        clearTimeout(timeoutId);
        console.warn('Image conversion timed out after 5 minutes.');
        finish();
      }
    };

    // Initial poll
    pollAndCheck();

    // If not done, set up polling interval
    if (!done) {
      conversionPollInterval = setInterval(pollAndCheck, 500); // Poll every 500ms
    }
  });
  isConverting.value = false;
  uploadProgress.value = 100;
  console.log('Image conversion complete!');
}

const handleFileSelect = async (file: File) => {
  console.log('handleFileSelect called with file:', file);
  
  if (!file) {
    console.warn('No file selected');
    return;
  }
  
  // Clear any previous error message
  errorMessage.value = '';
  
  isCreatingProject.value = true;
  try {
    if (routeProjectId && routeProjectId !== 'new') {
      // Existing project: upload video to this project
      console.log('Uploading to existing project:', routeProjectId);
      await uploadVideoFile(routeProjectId, file);
      if (errorMessage.value.length === 0) {
        console.log('Video upload complete!');
        await router.push({ name: 'Trim', params: { id: routeProjectId } });
      } else {
        console.log('Video upload failed...');
      }
    } else {
      // No project in route: create a new project from file name
      const filename = file.name.replace(/\.[^/.]+$/, '');
      const projectName = filename || 'Untitled Project';
      console.log('Creating project with name:', projectName);
      const created = await projectsStore.createProject(projectName, true);
      console.log('Project created:', created);
      if (created?.id) {
        console.log('Starting video upload...');
        await uploadVideoFile(created.id, file);
        if (errorMessage.value.length === 0) {
          console.log('Video upload complete!');
          console.log('Navigating to Trim stage...');
          await router.push({ name: 'Trim', params: { id: created.id } });
        } else {
          console.log('Video upload failed...');
        }
      } else {
        console.error('Project creation failed - no ID returned');
      }
    }
  } catch (error) {
    console.error('Failed to create project or upload video:', error);
    errorMessage.value = 'Failed to upload video. Please try again.';
  } finally {
    isCreatingProject.value = false;
    uploadProgress.value = 0;
    uploadMessage.value = '';
  }
};

// On entering Upload stage for an existing project, route to Trim if video exists
onMounted(async () => {
  // Mark upload stage as visited whenever this page is visited (new or existing project)
  if (routeProjectId && routeProjectId !== 'new') {
    await fetchProject();
    await markStageVisited();
  }
  
  // Check if project already has a video and redirect if so
  if (!routeProjectId || routeProjectId === 'new') return;
  
  try {
    const { data } = await api.get(`/projects/${routeProjectId}`);
    if (data?.video_path) {
      console.log('Project already has a video; redirecting to Trim.');
      await router.replace({ name: 'Trim', params: { id: routeProjectId } });
    }
  } catch (e) {
    console.warn('Could not fetch project for upload route:', e);
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
  margin: 1rem 1.25rem 1.25rem;
  width: calc(100% - 2.5rem);
  max-width: 1400px;
  transition: background var(--transition-duration, 0.2s) ease, box-shadow var(--transition-duration, 0.2s) ease, border-color var(--transition-duration, 0.2s) ease;
}

.hero__text { max-width: 720px; width: 100%; }
.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 700;
  font-size: 0.8rem;
  color: var(--muted, #5b6474);
  margin: 0 0 0.35rem;
}
h1 { margin: 0 0 0.25rem; font-size: 2rem; letter-spacing: -0.02em; }
.lede { margin: 0 0 0.75rem; color: var(--muted, #4b5563); line-height: 1.6; }
.hero__actions { display: flex; gap: 0.75rem; flex-wrap: wrap; justify-content: flex-end; }

.btn-icon { display: inline-flex; align-items: center; gap: 0.5rem; }
.ghost {
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #dfe3ec);
  color: var(--text, #0f172a);
  padding: 0.55rem 0.9rem;
  border-radius: 12px;
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
  transition: transform var(--transition-duration, 0.2s) ease, box-shadow var(--transition-duration, 0.2s) ease, background var(--transition-duration, 0.2s) ease;
}

.ghost:hover {
  transform: translateY(-2px);
}
.upload-card {
  width: 100%;
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 16px;
  padding: 1.5rem;
  background: var(--surface, #ffffff);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
  transition: box-shadow var(--transition-duration, 0.2s) ease, background var(--transition-duration, 0.2s) ease, border-color var(--transition-duration, 0.2s) ease;
}

.content { 
  width: calc(100% - 2.5rem); 
  max-width: 1400px;
  margin: 0 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  background: #fef2f2;
  border: 1px solid #fca5a5;
  border-radius: 12px;
  color: #991b1b;
  font-weight: 500;
}

.error-banner__icon {
  flex-shrink: 0;
  opacity: 0.8;
}

@media (max-width: 900px) {
  .hero { flex-direction: column; }
  .hero__actions { justify-content: flex-start; }
}
</style>
