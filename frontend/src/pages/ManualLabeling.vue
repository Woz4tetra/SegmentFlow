<template>
  <div class="manual-labeling-page">
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
        <p class="eyebrow">Stage: Manual Labeling</p>
        <h1>{{ project?.name ?? 'Loading...' }}</h1>
        <p class="lede">
          Click on the image to add labeled points. Use keyboard shortcuts for faster labeling.
        </p>
      </div>
    </section>

    <div v-if="loading" class="loading-container">
      <p>Loading project and images...</p>
    </div>

    <div v-else class="labeling-container">
      <!-- Image Viewer -->
      <div class="viewer-section">
        <ImageViewer 
          v-if="currentImage"
          :image-url="currentImageUrl"
          :width="viewerWidth"
          :height="viewerHeight"
        />
        <div v-else class="no-image">
          No images available. Please complete the trim stage first.
        </div>

        <!-- Viewer Controls -->
        <div class="viewer-controls">
          <button 
            @click="resetView" 
            class="control-btn"
            title="Reset view (R)"
          >
            <svg viewBox="0 0 24 24" width="16" height="16">
              <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" stroke="currentColor" stroke-width="2" fill="none" />
              <path d="M21 3v5h-5" stroke="currentColor" stroke-width="2" fill="none" />
            </svg>
            Reset View <span class="hotkey">R</span>
          </button>
        </div>
      </div>

      <!-- Control Panel -->
      <div class="control-panel">
        <!-- Frame Navigation -->
        <div class="control-section">
          <h3>Frame Navigation</h3>
          <div class="frame-nav">
            <input 
              type="number" 
              v-model.number="frameInput" 
              @keyup.enter="goToFrame"
              placeholder="Frame #"
              class="frame-input"
            />
            <button @click="goToFrame" class="btn-sm">Go</button>
          </div>
          <div class="nav-buttons">
            <button @click="previousFrame" class="btn-sm" title="Previous (←, A)">
              ← Previous <span class="hotkey">← A</span>
            </button>
            <button @click="nextFrame" class="btn-sm" title="Next (→, D)">
              Next → <span class="hotkey">→ D</span>
            </button>
          </div>
          <div class="nav-buttons">
            <button @click="previousLabeledFrame" class="btn-sm" title="Previous labeled (Q)">
              ⤎ Prev Labeled <span class="hotkey">Q</span>
            </button>
            <button @click="nextLabeledFrame" class="btn-sm" title="Next labeled (E)">
              Next Labeled ⤏ <span class="hotkey">E</span>
            </button>
          </div>
          <div class="nav-buttons">
            <button @click="bigJump" class="btn-sm" title="Big jump forward (N)">
              ⇥ Jump {{ bigJumpSize }} <span class="hotkey">N</span>
            </button>
          </div>
        </div>

        <!-- Frame Info -->
        <div class="control-section">
          <h3>Current Frame</h3>
          <div class="frame-info">
            <p><strong>Frame:</strong> {{ currentFrameNumber }} / {{ totalFrames }}</p>
            <p><strong>Status:</strong> {{ frameStatus }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { onMounted, onUnmounted, ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';
import StageNavigation from '../components/StageNavigation.vue';
import ImageViewer from '../components/ImageViewer.vue';

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
const router = useRouter();
const projectId = String(route.params.id ?? '');
const api = axios.create({ 
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1', 
  timeout: 20000 
});

const loading = ref(true);
const project = ref<Project | null>(null);
const currentFrameNumber = ref(1);
const totalFrames = ref(0);
const frameInput = ref<number | null>(null);
const viewerWidth = ref(1200);
const viewerHeight = ref(800);
const bigJumpSize = ref(100); // TODO: Load from config

const currentImage = computed(() => {
  // TODO: Load actual image data
  return currentFrameNumber.value <= totalFrames.value;
});

const currentImageUrl = computed(() => {
  // TODO: Construct actual image URL
  return `${import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'}/projects/${projectId}/frames/${currentFrameNumber.value}`;
});

const frameStatus = computed(() => {
  // TODO: Implement actual status tracking
  return 'Unlabeled';
});

async function fetchProject(): Promise<void> {
  try {
    const { data } = await api.get<Project>(`/projects/${projectId}`);
    project.value = data;
  } catch (error) {
    console.error('Failed to fetch project:', error);
  }
}

async function markStageVisited(): Promise<void> {
  try {
    await api.post(`/projects/${projectId}/mark_stage_visited?stage=manual_labeling`);
  } catch (error) {
    console.error('Failed to mark stage as visited:', error);
  }
}

function resetView(): void {
  // This will be handled by the ImageViewer component
  // For now, just emit an event or use a ref
  console.log('Reset view requested');
}

function goToFrame(): void {
  if (frameInput.value !== null && frameInput.value >= 1 && frameInput.value <= totalFrames.value) {
    currentFrameNumber.value = frameInput.value;
    frameInput.value = null;
  }
}

function nextFrame(): void {
  if (currentFrameNumber.value < totalFrames.value) {
    currentFrameNumber.value++;
  }
}

function previousFrame(): void {
  if (currentFrameNumber.value > 1) {
    currentFrameNumber.value--;
  }
}

function nextLabeledFrame(): void {
  // TODO: Implement finding next labeled frame
  console.log('Next labeled frame');
}

function previousLabeledFrame(): void {
  // TODO: Implement finding previous labeled frame
  console.log('Previous labeled frame');
}

function bigJump(): void {
  currentFrameNumber.value = Math.min(currentFrameNumber.value + bigJumpSize.value, totalFrames.value);
}

function handleKeyDown(event: KeyboardEvent): void {
  // Don't handle shortcuts if user is typing in an input
  if (event.target instanceof HTMLInputElement) {
    return;
  }

  switch (event.key.toLowerCase()) {
    case 'r':
      resetView();
      break;
    case 'arrowleft':
    case 'a':
      previousFrame();
      break;
    case 'arrowright':
    case 'd':
      nextFrame();
      break;
    case 'q':
      previousLabeledFrame();
      break;
    case 'e':
      nextLabeledFrame();
      break;
    case 'n':
      bigJump();
      break;
  }
}

onMounted(async () => {
  loading.value = true;
  await fetchProject();
  await markStageVisited();
  
  // TODO: Load frames and set totalFrames
  totalFrames.value = 100; // Placeholder
  
  loading.value = false;

  // Add keyboard event listener
  window.addEventListener('keydown', handleKeyDown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown);
});
</script>

<style scoped>
.manual-labeling-page {
  min-height: 100vh;
  background: var(--color-bg);
}

.hero {
  padding: 2rem;
  border-bottom: 1px solid var(--color-border);
}

.hero__text {
  max-width: 800px;
}

.eyebrow {
  font-size: 0.875rem;
  color: var(--color-primary);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.5rem;
}

.lede {
  color: var(--color-text-secondary);
  margin-top: 0.5rem;
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 4rem;
}

.labeling-container {
  display: grid;
  grid-template-columns: 1fr 350px;
  gap: 1rem;
  padding: 1rem;
  max-width: 1800px;
  margin: 0 auto;
}

.viewer-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.no-image {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 600px;
  background: var(--color-bg-secondary);
  border: 2px dashed var(--color-border);
  border-radius: 8px;
  color: var(--color-text-secondary);
}

.viewer-controls {
  display: flex;
  gap: 0.5rem;
  justify-content: center;
}

.control-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.control-btn:hover {
  background: var(--color-bg-tertiary);
}

.control-btn svg {
  color: currentColor;
  fill: none;
}

.control-panel {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: 1rem;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  height: fit-content;
}

.control-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.control-section h3 {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-text);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--color-border);
}

.frame-nav {
  display: flex;
  gap: 0.5rem;
}

.frame-input {
  flex: 1;
  padding: 0.5rem;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 0.875rem;
}

.frame-input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.nav-buttons {
  display: flex;
  gap: 0.5rem;
}

.btn-sm {
  flex: 1;
  padding: 0.5rem 0.75rem;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.btn-sm:hover {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
}

.hotkey {
  font-size: 0.75rem;
  color: var(--color-text-secondary);
  font-weight: 400;
}

.btn-sm:hover .hotkey {
  color: rgba(255, 255, 255, 0.7);
}

.frame-info {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.frame-info p {
  margin: 0;
  font-size: 0.875rem;
  color: var(--color-text);
}

.ghost {
  background: transparent;
  border: 1px solid var(--color-border);
  padding: 0.5rem 1rem;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  text-decoration: none;
  color: var(--color-text);
  font-size: 0.875rem;
  transition: all 0.2s;
}

.ghost:hover {
  background: var(--color-bg-secondary);
}

.icon {
  fill: none;
  stroke: currentColor;
}
</style>
