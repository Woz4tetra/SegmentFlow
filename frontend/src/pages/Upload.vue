<template>
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
    <div class="upload-card">
      <FileUpload
        :disabled="isCreatingProject"
        :is-uploading="isCreatingProject"
        :upload-progress="uploadProgress"
        :uploading-file-name="uploadingFileName"
        @file-selected="handleFileSelect"
      />
    </div>
  </section>
</template>

<script lang="ts" setup>
import { ref, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useProjectsStore } from '../stores/projects';
import FileUpload from '../components/FileUpload.vue';
import axios from 'axios';

const router = useRouter();
const route = useRoute();
const routeProjectId = route.params.id ? String(route.params.id) : '';
const projectsStore = useProjectsStore();
const isCreatingProject = ref(false);
const uploadProgress = ref(0);
const uploadingFileName = ref('');

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1',
  timeout: 30000,
});

// Compute SHA-256 hash of file contents (browser compatible)
async function computeFileHash(file: File): Promise<string> {
  console.log('Computing file hash...');
  const buffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  console.log('File hash (SHA-256):', hashHex);
  return hashHex;
}

// Upload file in chunks to backend
async function uploadVideoFile(projectId: string, file: File): Promise<void> {
  const CHUNK_SIZE = 10 * 1024 * 1024; // 10MB chunks
  const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
  
  console.log(`Uploading file: ${file.name}, size: ${file.size} bytes, chunks: ${totalChunks}`);
  
  // Reset progress
  uploadProgress.value = 0;
  uploadingFileName.value = file.name;
  
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
  
  // Upload chunks (10-90% progress)
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
    
    // Update progress: 10% to 90% based on chunks uploaded
    const chunkProgress = ((i + 1) / totalChunks) * 80;
    uploadProgress.value = 10 + Math.round(chunkProgress);
    
    console.log(`Chunk ${i} uploaded successfully`);
  }
  
  // Complete upload (90-100% progress)
  uploadProgress.value = 90;
  console.log('Completing upload...');
  await api.post(`/projects/${projectId}/upload/complete`);
  uploadProgress.value = 100;
  console.log('Upload completed successfully!');
}

const handleFileSelect = async (file: File) => {
  console.log('handleFileSelect called with file:', file);
  
  if (!file) {
    console.warn('No file selected');
    return;
  }
  
  isCreatingProject.value = true;
  try {
    if (routeProjectId && routeProjectId !== 'new') {
      // Existing project: upload video to this project
      console.log('Uploading to existing project:', routeProjectId);
      await uploadVideoFile(routeProjectId, file);
      console.log('Video upload complete!');
      await router.push({ name: 'Trim', params: { id: routeProjectId } });
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
        console.log('Video upload complete!');
        console.log('Navigating to Trim stage...');
        await router.push({ name: 'Trim', params: { id: created.id } });
      } else {
        console.error('Project creation failed - no ID returned');
      }
    }
  } catch (error) {
    console.error('Failed to create project or upload video:', error);
  } finally {
    isCreatingProject.value = false;
    uploadProgress.value = 0;
    uploadingFileName.value = '';
  }
};

// On entering Upload stage for an existing project, route to Trim if video exists
onMounted(async () => {
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
  margin-bottom: 1.25rem;
  width: 100%;
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
  width: 100%; 
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

@media (max-width: 900px) {
  .hero { flex-direction: column; }
  .hero__actions { justify-content: flex-start; }
}
</style>
