<template>
  <div class="manual-labeling-page" :class="{ 'fullscreen': !sidebarVisible }">
    <!-- Stage Navigation -->
    <StageNavigation v-if="project && sidebarVisible" :project="project" />

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

    <div v-else class="content-wrapper">
      <div class="labeling-container" :class="{ 'sidebar-hidden': !sidebarVisible }">
      <!-- Image Viewer -->
      <div class="viewer-section">
        <ImageViewer 
          v-if="currentImage"
          :image-url="currentImageUrl"
          :width="viewerWidth"
          :height="viewerHeight"
          :project-id="projectId"
          :frame-number="currentFrameNumber"
          :selected-label-id="selectedLabel?.id"
          :selected-label-color="selectedLabel?.color_hex || '#2563eb'"
        />
        <div v-else class="no-image">
          No images available. Please complete the trim stage first.
        </div>

        <!-- Viewer Controls -->
        <div class="viewer-controls">
          <button 
            @click="toggleSidebar" 
            class="control-btn"
            :title="sidebarVisible ? 'Hide sidebar (F)' : 'Show sidebar (F)'"
          >
            <svg v-if="sidebarVisible" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 18l-6-6 6-6M21 18l-6-6 6-6" />
            </svg>
            <svg v-else viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M15 18l6-6-6-6M3 18l6-6-6-6" />
            </svg>
            {{ sidebarVisible ? 'Hide Sidebar' : 'Show Sidebar' }} <span class="hotkey">F</span>
          </button>
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
      <div v-if="sidebarVisible" class="control-panel">
        <!-- Frame Navigation -->
        <div class="control-section">
          <h3>Frame Navigation</h3>
          
          <!-- Jump to frame input -->
          <div class="frame-nav">
            <input 
              type="number" 
              v-model.number="frameInput" 
              @keyup.enter="goToFrame"
              placeholder="Go to frame"
              class="frame-input"
            />
            <button @click="goToFrame" class="btn-go">Go</button>
          </div>
          
          <!-- Primary navigation buttons -->
          <div class="nav-buttons-primary">
            <button @click="previousFrame" class="btn-nav btn-nav-prev" title="Previous frame (← or A)">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M15 19l-7-7 7-7"/>
              </svg>
              Previous
              <span class="hotkey">← A</span>
            </button>
            <button @click="nextFrame" class="btn-nav btn-nav-next" title="Next frame (→ or D)">
              Next
              <span class="hotkey">→ D</span>
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 5l7 7-7 7"/>
              </svg>
            </button>
          </div>
          
          <!-- Secondary navigation buttons -->
          <div class="nav-buttons-secondary">
            <button @click="previousLabeledFrame" class="btn-sm" title="Previous labeled frame (Q)">
              ⤎ Prev Labeled <span class="hotkey">Q</span>
            </button>
            <button @click="nextLabeledFrame" class="btn-sm" title="Next labeled frame (E)">
              Next Labeled ⤏ <span class="hotkey">E</span>
            </button>
          </div>
          
          <!-- Big jump button -->
          <button @click="bigJump" class="btn-sm btn-jump" title="Jump forward (N)">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M5 12h14M12 5l7 7-7 7"/>
            </svg>
            Jump +{{ bigJumpSize }} <span class="hotkey">N</span>
          </button>
        </div>

        <!-- Frame Info -->
        <div class="control-section">
          <h3>Current Frame</h3>
          <div class="frame-info">
            <div class="frame-info-row">
              <span>Frame Number</span>
              <strong>{{ currentFrameNumber }} / {{ totalFrames }}</strong>
            </div>
            <div class="frame-info-row">
              <span>Status</span>
              <strong class="status-badge">{{ frameStatus }}</strong>
            </div>
          </div>
        </div>

        <!-- Label Selection -->
        <div class="control-section">
          <h3>Active Label</h3>
          <div v-if="labels.length === 0" class="no-labels">
            <p>No labels available</p>
            <p class="hint">Create labels in the Labels page first</p>
          </div>
          <div v-else class="label-selector">
            <div 
              v-for="label in labels" 
              :key="label.id"
              @click="selectLabel(label)"
              @mouseenter="hoveredLabelId = label.id"
              @mouseleave="hoveredLabelId = null"
              :class="['label-option', { active: selectedLabel?.id === label.id }]"
            >
              <div class="label-color" :style="{ backgroundColor: label.color_hex }"></div>
              <span class="label-name">{{ label.name }}</span>
              <!-- CANVAS-006: Thumbnail preview on hover -->
              <div 
                v-if="hoveredLabelId === label.id && label.thumbnail_path" 
                class="label-thumbnail-preview"
              >
                <img 
                  :src="label.thumbnail_path" 
                  :alt="`${label.name} thumbnail`"
                  @error="handleThumbnailError"
                />
              </div>
            </div>
          </div>
          <div v-if="selectedLabel" class="mode-info">
            <p class="mode-label">Click Mode:</p>
            <p class="mode-keys">
              <kbd>I</kbd> Include • <kbd>U</kbd> Exclude
            </p>
          </div>
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

interface ImageData {
  id: string;
  frame_number: number;
  inference_path: string | null;
  output_path: string | null;
  status: string;
  manually_labeled: boolean;
  validation: string;
}

interface Label {
  id: string;
  name: string;
  color_hex: string;
  thumbnail_path: string | null;
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
const images = ref<ImageData[]>([]);
const labels = ref<Label[]>([]);
const selectedLabel = ref<Label | null>(null);
const currentFrameNumber = ref(0);
const totalFrames = ref(0);
const frameInput = ref<number | null>(null);
const viewerWidth = ref(1200);
const viewerHeight = ref(800);
const bigJumpSize = ref(100); // TODO[NAV-004]: Load from config
const hoveredLabelId = ref<string | null>(null); // Track which label is being hovered
const sidebarVisible = ref(true); // Sidebar visibility state

const currentImage = computed(() => {
  if (images.value.length === 0) return null;
  const img = images.value.find(img => img.frame_number === currentFrameNumber.value);
  console.log('currentImage computed:', { 
    frameNumber: currentFrameNumber.value, 
    found: !!img,
    totalImages: images.value.length 
  });
  return img;
});

const currentImageUrl = computed(() => {
  // CANVAS-003: Construct image URL from backend endpoint
  return `${import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'}/projects/${projectId}/frames/${currentFrameNumber.value}`;
});

const frameStatus = computed(() => {
  if (!currentImage.value) return 'No Image';
  
  // Determine status based on image data
  if (currentImage.value.validation === 'passed') {
    return 'Validated';
  } else if (currentImage.value.validation === 'failed') {
    return 'Failed Validation';
  } else if (currentImage.value.manually_labeled) {
    return 'Manually Labeled';
  } else if (currentImage.value.status === 'processed') {
  return 'Unlabeled';
  } else if (currentImage.value.status === 'pending') {
    return 'Processing';
  } else if (currentImage.value.status === 'failed') {
    return 'Processing Failed';
  }
  
  return 'Unknown';
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
    const { data } = await api.post<Project>(`/projects/${projectId}/mark_stage_visited?stage=manual_labeling`);
    // Update local project data with response
    if (data) {
      project.value = data;
    }
  } catch (error) {
    console.error('Failed to mark stage as visited:', error);
  }
}

async function fetchLabels(): Promise<void> {
  try {
    console.log('Fetching labels');
    const { data } = await api.get<Label[]>('/labels');
    console.log('Fetched labels:', data.length);
    labels.value = data || [];
    
    // Auto-select first label if available
    if (labels.value.length > 0 && !selectedLabel.value) {
      selectedLabel.value = labels.value[0];
      console.log('Auto-selected first label:', selectedLabel.value.name);
    }
  } catch (error) {
    console.error('Failed to fetch labels:', error);
    labels.value = [];
  }
}

function selectLabel(label: Label): void {
  selectedLabel.value = label;
  console.log('Selected label:', label.name);
}

function handleThumbnailError(event: Event): void {
  // Hide broken thumbnail images
  const img = event.target as HTMLImageElement;
  if (img && img.parentElement) {
    img.parentElement.style.display = 'none';
  }
}

function resetView(): void {
  // This will be handled by the ImageViewer component
  // For now, just emit an event or use a ref
  console.log('Reset view requested');
}

function toggleSidebar(): void {
  sidebarVisible.value = !sidebarVisible.value;
}

async function fetchImages(): Promise<void> {
  try {
    console.log('Fetching images for project:', projectId);
    const { data } = await api.get<{ images: ImageData[]; total: number }>(`/projects/${projectId}/images`);
    console.log('Fetched images:', { total: data.total, count: data.images?.length });
    images.value = data.images || [];
    totalFrames.value = data.total || 0;
    
    // Set current frame to first available frame
    if (images.value.length > 0) {
      currentFrameNumber.value = images.value[0].frame_number;
      console.log('Set current frame to:', currentFrameNumber.value);
    } else {
      console.warn('No images found for project');
    }
  } catch (error) {
    console.error('Failed to fetch images:', error);
    images.value = [];
    totalFrames.value = 0;
  }
}

function goToFrame(): void {
  if (frameInput.value !== null) {
    const targetFrame = images.value.find(img => img.frame_number === frameInput.value);
    if (targetFrame) {
    currentFrameNumber.value = frameInput.value;
    frameInput.value = null;
    }
  }
}

function nextFrame(): void {
  const currentIndex = images.value.findIndex(img => img.frame_number === currentFrameNumber.value);
  if (currentIndex >= 0 && currentIndex < images.value.length - 1) {
    currentFrameNumber.value = images.value[currentIndex + 1].frame_number;
  }
}

function previousFrame(): void {
  const currentIndex = images.value.findIndex(img => img.frame_number === currentFrameNumber.value);
  if (currentIndex > 0) {
    currentFrameNumber.value = images.value[currentIndex - 1].frame_number;
  }
}

function nextLabeledFrame(): void {
  // TODO[NAV-003]: Implement finding next labeled frame
  console.log('Next labeled frame');
}

function previousLabeledFrame(): void {
  // TODO[NAV-003]: Implement finding previous labeled frame
  console.log('Previous labeled frame');
}

function bigJump(): void {
  const currentIndex = images.value.findIndex(img => img.frame_number === currentFrameNumber.value);
  if (currentIndex >= 0) {
    const targetIndex = Math.min(currentIndex + bigJumpSize.value, images.value.length - 1);
    currentFrameNumber.value = images.value[targetIndex].frame_number;
  }
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
    case 'f':
    case 'F':
      toggleSidebar();
      break;
  }
}

onMounted(async () => {
  loading.value = true;
  
  try {
    // Mark all previous stages as visited to ensure they're in the visited state
    const uploadRes = await api.post<Project>(`/projects/${projectId}/mark_stage_visited?stage=upload`);
    if (uploadRes.data) {
      project.value = uploadRes.data;
    }
    
    const trimRes = await api.post<Project>(`/projects/${projectId}/mark_stage_visited?stage=trim`);
    if (trimRes.data) {
      project.value = trimRes.data;
    }
    
    // Mark this stage as visited
    const manualRes = await api.post<Project>(`/projects/${projectId}/mark_stage_visited?stage=manual_labeling`);
    if (manualRes.data) {
      project.value = manualRes.data;
    }
    
    // Load images and labels from backend
    await Promise.all([fetchImages(), fetchLabels()]);
  } catch (error) {
    console.error('Failed during initialization:', error);
  }
  
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
  background: var(--bg, #f5f7fb);
  transition: all 0.3s ease;
}

.manual-labeling-page.fullscreen {
  padding: 0;
}

.manual-labeling-page.fullscreen .content-wrapper {
  padding: 0;
  max-width: 100%;
}

.manual-labeling-page.fullscreen .hero {
  margin: 0;
  border-radius: 0;
  width: 100%;
  max-width: 100%;
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
  transition: background 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.content-wrapper {
  width: 100%;
  display: flex;
  justify-content: center;
  padding: 1.5rem 1.25rem;
  background: var(--bg, #f5f7fb);
  transition: padding 0.3s ease;
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
  justify-content: center;
  align-items: center;
  padding: 4rem;
  color: var(--muted, #4b5563);
}

.labeling-container {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 1.5rem;
  padding: 0;
  width: 100%;
  max-width: 1400px;
  transition: grid-template-columns 0.3s ease;
}

.labeling-container.sidebar-hidden {
  grid-template-columns: 1fr;
  max-width: 100%;
}

.viewer-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-width: 0; /* Allow flex item to shrink */
  max-width: 100%; /* Prevent overflow */
  overflow: hidden; /* Prevent content from overflowing */
}

.no-image {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 700px;
  background: var(--surface-muted, #eef2f7);
  border: 2px dashed var(--border, #dfe3ec);
  border-radius: 16px;
  color: var(--muted, #6b7280);
  font-size: 1rem;
  font-weight: 500;
}

.viewer-controls {
  display: flex;
  gap: 0.75rem;
  justify-content: center;
}

.control-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 1.2rem;
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 12px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--text, #0f172a);
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.control-btn:hover {
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: #ffffff;
  border-color: transparent;
  box-shadow: 0 6px 20px rgba(37, 99, 235, 0.25);
  transform: translateY(-2px);
}

.control-btn svg {
  width: 18px;
  height: 18px;
  color: currentColor;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
}

.control-panel {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: 1.25rem;
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 16px;
  height: fit-content;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.control-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.control-section h3 {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--text, #0f172a);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin: 0;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border, #e5e7eb);
}

.frame-nav {
  display: flex;
  gap: 0.5rem;
}

.frame-input {
  flex: 1;
  padding: 0.65rem 0.9rem;
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 10px;
  background: var(--surface, #ffffff);
  color: var(--text, #0f172a);
  font-size: 0.9rem;
  font-weight: 500;
  transition: all 0.2s ease;
}

.frame-input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.frame-input::placeholder {
  color: var(--muted, #9ca3af);
}

.nav-buttons {
  display: flex;
  gap: 0.5rem;
  flex-direction: column;
}

.nav-buttons-primary {
  display: flex;
  gap: 0.6rem;
  flex-direction: column;
}

.btn-nav {
  padding: 0.85rem 1rem;
  background: var(--surface-muted, #f3f4f6);
  border: 1.5px solid var(--border, #dfe3ec);
  border-radius: 12px;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text, #0f172a);
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.btn-nav svg {
  color: currentColor;
  fill: none;
}

.btn-nav:hover {
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: white;
  border-color: transparent;
  box-shadow: 0 6px 20px rgba(37, 99, 235, 0.25);
  transform: translateY(-2px);
}

.btn-nav .hotkey {
  margin-left: auto;
  font-size: 0.7rem;
  color: var(--muted, #9ca3af);
  font-weight: 500;
}

.btn-nav:hover .hotkey {
  color: rgba(255, 255, 255, 0.8);
}

.nav-buttons-secondary {
  display: flex;
  gap: 0.5rem;
  flex-direction: column;
}

.btn-go {
  padding: 0.65rem 1.2rem;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: white;
  border: 1px solid transparent;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.2);
}

.btn-go:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(37, 99, 235, 0.3);
}

.btn-sm {
  flex: 1;
  padding: 0.75rem 0.9rem;
  background: var(--surface-muted, #f3f4f6);
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 10px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text, #0f172a);
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  white-space: nowrap;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
}

.btn-sm:hover {
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: white;
  border-color: transparent;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
  transform: translateY(-1px);
}

.btn-sm.btn-jump {
  gap: 0.6rem;
}

.btn-sm.btn-jump svg {
  color: currentColor;
  fill: none;
}

.hotkey {
  font-size: 0.7rem;
  color: var(--muted, #9ca3af);
  font-weight: 500;
  margin-left: 0.2rem;
  opacity: 0.8;
}

.btn-sm:hover .hotkey,
.btn-nav:hover .hotkey {
  color: rgba(255, 255, 255, 0.85);
}

.frame-info {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}

.frame-info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem;
  background: var(--surface-muted, #f9fafb);
  border-radius: 10px;
  border: 1px solid var(--border, #e5e7eb);
}

.frame-info-row span {
  font-size: 0.85rem;
  color: var(--muted, #6b7280);
  font-weight: 500;
}

.frame-info-row strong {
  font-size: 0.95rem;
  color: var(--text, #0f172a);
  font-weight: 700;
}

.status-badge {
  display: inline-block;
  padding: 0.3rem 0.8rem;
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.1), rgba(124, 58, 237, 0.05));
  border-radius: 6px;
  color: #2563eb !important;
  font-weight: 600;
  font-size: 0.8rem;
  text-transform: capitalize;
}

.no-labels {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 1rem;
  background: var(--surface-muted, #f9fafb);
  border-radius: 10px;
  border: 1px solid var(--border, #e5e7eb);
  text-align: center;
}

.no-labels p {
  margin: 0;
  font-size: 0.85rem;
  color: var(--muted, #6b7280);
}

.no-labels .hint {
  font-size: 0.75rem;
  color: var(--muted, #9ca3af);
}

.label-selector {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.label-option {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  background: var(--surface-muted, #f9fafb);
  border: 2px solid var(--border, #e5e7eb);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.label-option:hover {
  background: var(--surface, #ffffff);
  border-color: #2563eb;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15);
}

.label-option.active {
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.1), rgba(124, 58, 237, 0.05));
  border-color: #2563eb;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
}

.label-color {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 2px solid rgba(255, 255, 255, 0.9);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
  flex-shrink: 0;
}

.label-name {
  flex: 1;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text, #0f172a);
}

/* CANVAS-006: Label thumbnail preview on hover */
.label-option {
  position: relative;
}

.label-thumbnail-preview {
  position: absolute;
  left: calc(100% + 1rem);
  top: 50%;
  transform: translateY(-50%);
  z-index: 1000;
  pointer-events: none;
  animation: fadeIn 0.2s ease-in-out;
  /* Prevent thumbnail from going off-screen */
  max-width: 200px;
  max-height: 200px;
}

.label-thumbnail-preview::before {
  content: '';
  position: absolute;
  left: -8px;
  top: 50%;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  border-style: solid;
  border-width: 8px 8px 8px 0;
  border-color: transparent rgba(0, 0, 0, 0.15) transparent transparent;
  filter: drop-shadow(-2px 0 2px rgba(0, 0, 0, 0.1));
}

.label-thumbnail-preview img {
  width: 200px;
  height: 200px;
  object-fit: cover;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
  border: 3px solid #ffffff;
  background: var(--surface, #ffffff);
  display: block;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-50%) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(-50%) scale(1);
  }
}

/* Adjust thumbnail position for last item to prevent overflow */
.label-selector {
  position: relative;
  overflow: visible;
}

/* For the last label, show thumbnail above to prevent going off-screen */
.label-option:last-child .label-thumbnail-preview {
  top: auto;
  bottom: 0;
  transform: translateY(0);
  left: calc(100% + 1rem);
}

.label-option:last-child .label-thumbnail-preview::before {
  top: auto;
  bottom: 1rem;
  transform: translateY(0);
  border-width: 0 8px 8px 8px;
  border-color: transparent transparent rgba(0, 0, 0, 0.15) transparent;
  left: -8px;
  filter: drop-shadow(0 2px 2px rgba(0, 0, 0, 0.1));
}

.mode-info {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.05), rgba(124, 58, 237, 0.03));
  border-radius: 10px;
  border: 1px solid var(--border, #e5e7eb);
}

.mode-label {
  margin: 0 0 0.4rem;
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--muted, #6b7280);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.mode-keys {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text, #0f172a);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.mode-keys kbd {
  display: inline-block;
  padding: 0.25rem 0.5rem;
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 6px;
  font-family: 'Courier New', monospace;
  font-size: 0.8rem;
  font-weight: 600;
  color: #2563eb;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
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

@media (max-width: 1200px) {
  .labeling-container {
    grid-template-columns: 1fr 280px;
  }
}

@media (max-width: 768px) {
  .labeling-container {
    grid-template-columns: 1fr;
  }
  
  .control-panel {
    order: -1;
  }
}
</style>
