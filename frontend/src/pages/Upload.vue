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
      <div class="upload-area">
        <input
          ref="fileInputRef"
          id="videoFileInput"
          type="file"
          accept="video/*"
          style="display: none"
          @change="handleFileSelect"
        />
        <button
          class="upload-button"
          :disabled="isCreatingProject"
          @click="triggerFileInput"
          type="button"
        >
          {{ isCreatingProject ? 'Uploading video...' : 'Select Video File' }}
        </button>
        <p class="upload-hint">Supported formats: MP4, AVI, MOV</p>
      </div>
    </div>
  </section>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useProjectsStore } from '../stores/projects';
import axios from 'axios';

const router = useRouter();
const projectsStore = useProjectsStore();
const isCreatingProject = ref(false);
const fileInputRef = ref<HTMLInputElement | null>(null);

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
  
  // Compute file hash
  console.log('Computing file hash...');
  const fileHash = await computeFileHash(file);
  console.log('File hash:', fileHash);
  
  // Initialize upload session
  console.log('Initializing upload session...');
  await api.post(`/projects/${projectId}/upload/init`, null, {
    params: {
      total_chunks: totalChunks,
      total_size: file.size,
      file_hash: fileHash,
    },
  });
  console.log('Upload session initialized');
  
  // Upload chunks
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
    
    console.log(`Chunk ${i} uploaded successfully`);
  }
  
  // Complete upload
  console.log('Completing upload...');
  await api.post(`/projects/${projectId}/upload/complete`);
  console.log('Upload completed successfully!');
}

const handleFileSelect = async (event: Event) => {
  console.log('handleFileSelect called with event:', event);
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  
  console.log('Selected file:', file);
  if (!file) {
    console.warn('No file selected');
    return;
  }
  
  // Extract filename without extension as project name
  const filename = file.name.replace(/\.[^/.]+$/, '');
  const projectName = filename || 'Untitled Project';
  console.log('Creating project with name:', projectName);
  
  isCreatingProject.value = true;
  try {
    // Step 1: Create project
    const created = await projectsStore.createProject(projectName, true);
    console.log('Project created:', created);
    
    if (created?.id) {
      // Step 2: Upload the video file
      console.log('Starting video upload...');
      await uploadVideoFile(created.id, file);
      console.log('Video upload complete!');
      
      // Step 3: Clear input
      if (fileInputRef.value) {
        fileInputRef.value.value = '';
      }
      
      // Step 4: Navigate to the project (or next stage)
      console.log('Navigating to project...');
      await router.push({ name: 'Home' });
    } else {
      console.error('Project creation failed - no ID returned');
    }
  } catch (error) {
    console.error('Failed to create project or upload video:', error);
    // Clear input on error too
    if (fileInputRef.value) {
      fileInputRef.value.value = '';
    }
  } finally {
    isCreatingProject.value = false;
  }
};

const triggerFileInput = () => {
  if (fileInputRef.value) {
    console.log('Found file input element, clicking it');
    fileInputRef.value.click();
    console.log('File input clicked successfully');
  } else {
    console.error('Could not find file input element');
  }
};
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
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}

.ghost:hover {
  transform: translateY(-2px);
}
.upload-card {
  width: 100%;
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 16px;
  padding: 1rem 1.25rem;
  background: var(--surface, #ffffff);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
}

@media (max-width: 900px) {
  .hero { flex-direction: column; }
  .hero__actions { justify-content: flex-start; }
}

.upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.upload-button {
  padding: 0.7rem 1.2rem;
  border-radius: 12px;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: #ffffff;
  font-weight: 600;
  border: 1px solid rgba(124, 58, 237, 0.35);
  cursor: pointer;
  box-shadow: 0 10px 30px rgba(37, 99, 235, 0.28);
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}

.upload-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 14px 36px rgba(37, 99, 235, 0.35);
}

.upload-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.upload-hint {
  color: var(--muted, #4b5563);
  font-size: 0.9rem;
  margin: 0;
}
</style>
