<template>
  <!-- Top hero: same width and style approach as Home hero -->
  <section class="hero">
    <div class="hero__text">
      <p class="eyebrow">Create Project</p>
      <h1>Upload Video</h1>
      <p class="lede">
        Select a video file to create a new annotation project. Your project will be named based on the video filename.
      </p>
    </div>
    <div class="hero__actions">
      <router-link to="/" class="ghost btn-icon" title="Back to Projects">
        <svg class="icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
          <path d="M15 19l-7-7 7-7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <span>Back to Projects</span>
      </router-link>
    </div>
  </section>

  <!-- Main upload card: full-width like Home hero card -->
  <section class="content">
    <div class="upload-card">
      <div class="upload-area">
        <input
          ref="fileInput"
          type="file"
          accept="video/*"
          style="display: none"
          @change="handleFileSelect"
        />
        <button
          class="upload-button"
          :disabled="isCreatingProject"
          @click="triggerFileInput"
        >
          {{ isCreatingProject ? 'Creating project...' : 'Select Video File' }}
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

const router = useRouter();
const projectsStore = useProjectsStore();
const fileInput = ref<HTMLInputElement | null>(null);
const isCreatingProject = ref(false);

const handleFileSelect = async (event: Event) => {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  
  if (!file) return;
  
  // Extract filename without extension as project name
  const filename = file.name.replace(/\.[^/.]+$/, '');
  const projectName = filename || 'Untitled Project';
  
  isCreatingProject.value = true;
  try {
    const created = await projectsStore.createProject(projectName, true);
    if (created?.id) {
      // Project created successfully, reset form
      fileInput.value = null;
    }
  } finally {
    isCreatingProject.value = false;
  }
};

const triggerFileInput = () => {
  fileInput.value?.click();
};
</script>

<style scoped>
.hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.5rem;
  padding: 1.25rem 1.5rem;
  border: 1px solid var(--border, #dfe3ec);
  background: var(--surface, #ffffff);
  border-radius: 18px;
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.06);
  margin-bottom: 1.25rem;
  width: 100%;
}

.hero__text { max-width: 720px; }
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
