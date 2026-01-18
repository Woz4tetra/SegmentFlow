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
        <p class="eyebrow">Stage: {{ isValidationMode ? 'Validation' : 'Manual Labeling' }}</p>
        <h1>{{ project?.name ?? 'Loading...' }}</h1>
        <p class="lede">
          {{ isValidationMode
            ? 'Review propagated masks and mark each frame as pass or fail.'
            : 'Click on the image to add labeled points. Use keyboard shortcuts for faster labeling.'
          }}
        </p>
      </div>
    </section>

    <div v-if="loading" class="loading-container">
      <p>Loading project and images...</p>
    </div>

    <div v-else class="content-wrapper">
      <div class="labeling-container" :class="{ 'sidebar-hidden': !sidebarVisible }">
      <!-- Frame Status Slider (PROP-UI-004) -->
      <div class="slider-wrapper">
        <FrameStatusSlider 
          :images="imagesWithMaskStatus"
          :current-frame="currentFrameNumber"
          :total-frames="totalFrames"
          @frame-click="goToFrameFromSlider"
        />
      </div>
      <!-- Image Viewer -->
      <div class="viewer-section">
        <ImageViewer 
          ref="imageViewerRef"
          v-if="currentImage"
          :image-url="currentImageUrl"
          :width="viewerWidth"
          :height="viewerHeight"
          :project-id="projectId"
          :frame-number="currentFrameNumber"
          :selected-label-id="selectedLabel?.id"
          :selected-label-color="selectedLabel?.color_hex || '#2563eb'"
          :labels="labels"
          @frame-labeled="onFrameLabeled"
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
        <!-- Left Column: Navigation & Propagation -->
        <div class="control-column">
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
                <span>Frame</span>
                <strong>{{ currentFrameIndexLabel }}</strong>
              </div>
              <div class="frame-info-row">
                <span>Status</span>
                <strong class="status-badge">{{ frameStatus }}</strong>
              </div>
            </div>
          </div>

          <!-- Validation Panel (VAL-001/VAL-002) -->
          <div v-if="isValidationMode" class="control-section validation-section">
            <h3>Validation</h3>
            <p class="section-description">
              Mark the current frame as passed or failed after review.
            </p>
            <div class="validation-status">
              <span>Status</span>
              <strong class="validation-pill" :data-status="currentImage?.validation ?? 'not_validated'">
                {{ validationLabel }}
              </strong>
            </div>
            <div class="validation-actions">
              <button
                class="btn-validate btn-pass"
                type="button"
                :disabled="!currentImage || currentImage.manually_labeled || validationBusy"
                title="Pass validation (Z)"
                @click="setValidationStatus('passed')"
              >
                Pass <span class="hotkey">Z</span>
              </button>
              <button
                class="btn-validate btn-fail"
                type="button"
                :disabled="!currentImage || currentImage.manually_labeled || validationBusy"
                title="Fail validation (X)"
                @click="setValidationStatus('failed')"
              >
                Fail <span class="hotkey">X</span>
              </button>
            </div>
          </div>

          <!-- Auto Label Section (PROP-UI-003) -->
          <div class="control-section auto-label-section">
            <h3>Propagation</h3>
            <p class="section-description">
              Automatically propagate labels to all frames using SAM3.
            </p>
            <div class="labeled-frames-info" v-if="labeledFrameCount > 0">
              <span class="info-icon">✓</span>
              <span>{{ labeledFrameCount }} frame{{ labeledFrameCount !== 1 ? 's' : '' }} labeled</span>
            </div>
            <div class="labeled-frames-info warning" v-else>
              <span class="info-icon">!</span>
              <span>Label at least 1 frame first</span>
            </div>
            <button 
              @click="handlePrepareAction"
              :class="['btn-auto-label', { 'btn-auto-label--export': isValidationMode }]"
              :disabled="labeledFrameCount === 0"
              :title="labeledFrameCount === 0 ? 'Label at least one frame first' : isValidationMode ? 'Go to export' : 'Start automatic label propagation'"
            >
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="5,3 19,12 5,21" fill="currentColor" stroke="none" />
              </svg>
              {{ isValidationMode ? 'Prepare Export' : 'Prepare Auto Labeling' }}
            </button>
          </div>
        </div>

        <!-- Right Column: Label Selection -->
        <div class="control-column">
          <div class="control-section">
            <div class="section-header">
              <h3>Active Label</h3>
              <span class="section-hint"><kbd>T</kbd> cycle</span>
            </div>
            <div v-if="enabledLabels.length === 0" class="no-labels">
              <p>No enabled labels</p>
              <p class="hint">Enable labels in the Trim stage or create new labels first</p>
            </div>
            <div v-else class="label-selector">
              <div 
                v-for="label in enabledLabels" 
                :key="label.id"
                :class="['label-option', { active: selectedLabel?.id === label.id }]"
              >
                <div 
                  class="label-option-content"
                  @click="selectLabel(label)"
                  @mouseenter="hoveredLabelId = label.id"
                  @mouseleave="hoveredLabelId = null"
                >
                  <div class="label-color" :style="{ backgroundColor: label.color_hex }"></div>
                  <span class="label-name">{{ label.name }}</span>
                </div>
                <button 
                  @click.stop="clearLabelFromFrame(label.id)"
                  class="btn-clear-label"
                  title="Clear this label from current frame"
                >
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 6L6 18M6 6l12 12"/>
                  </svg>
                </button>
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
              <!-- Clear All Button -->
              <button 
                @click="showClearAllConfirm = true"
                class="btn-clear-all"
                title="Clear all labels from current frame"
              >
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6h14"/>
                </svg>
                Clear All Labels
              </button>
            </div>
            <div v-if="selectedLabel" class="mode-info">
              <p class="mode-label">Click Mode:</p>
              <div class="mode-keys">
                <span class="mode-key"><kbd>I</kbd> Include</span>
                <span class="mode-key"><kbd>U</kbd> Exclude</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    </div>

    <!-- Clear All Confirmation Dialog -->
    <Teleport to="body">
      <div v-if="showClearAllConfirm" class="modal-overlay" @click.self="showClearAllConfirm = false">
        <div class="modal-dialog">
          <h3>Clear All Labels?</h3>
          <p>This will remove all labeled points and masks from frame {{ currentFrameNumber }}. This action cannot be undone.</p>
          <div class="modal-actions">
            <button @click="showClearAllConfirm = false" class="btn-cancel">Cancel</button>
            <button @click="clearAllLabelsFromFrame" class="btn-confirm-delete">Clear All</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script lang="ts" setup>
import { onMounted, onUnmounted, ref, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';
import { API_BASE_URL, buildApiUrl } from '../lib/api';
import StageNavigation from '../components/StageNavigation.vue';
import ImageViewer from '../components/ImageViewer.vue';
import FrameStatusSlider from '../components/FrameStatusSlider.vue';

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
  has_mask?: boolean;
}

interface Label {
  id: string;
  name: string;
  color_hex: string;
  thumbnail_path: string | null;
}

interface LabelSetting extends Label {
  enabled: boolean;
}

interface FrameStatusData {
  frame_number: number;
  status: string;
  manually_labeled: boolean;
  validation: string;
  has_mask: boolean;
}

const route = useRoute();
const router = useRouter();
const projectId = String(route.params.id ?? '');
const api = axios.create({ 
  baseURL: API_BASE_URL, 
  timeout: 20000 
});

const loading = ref(true);
const project = ref<Project | null>(null);
const images = ref<ImageData[]>([]);
const labels = ref<LabelSetting[]>([]);
const selectedLabel = ref<LabelSetting | null>(null);
const currentFrameNumber = ref(0);
const totalFrames = ref(0);
const frameInput = ref<number | null>(null);
const viewerWidth = ref(1200);
const viewerHeight = ref(800);
const bigJumpSize = ref(500); // Default value, will be loaded from server config
const hoveredLabelId = ref<string | null>(null); // Track which label is being hovered
const sidebarVisible = ref(true); // Sidebar visibility state
const showClearAllConfirm = ref(false); // Clear all confirmation dialog
const imageViewerRef = ref<InstanceType<typeof ImageViewer> | null>(null); // Ref to ImageViewer component
const validationBusy = ref(false);

const isValidationMode = computed(() => route.name === 'Validation');
const enabledLabels = computed(() => labels.value.filter(label => label.enabled));

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
  return buildApiUrl(`/projects/${projectId}/frames/${currentFrameNumber.value}`);
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

const currentFrameIndex = computed(() => {
  if (images.value.length === 0) return -1;
  return images.value.findIndex(img => img.frame_number === currentFrameNumber.value);
});

const currentFrameIndexLabel = computed(() => {
  if (images.value.length === 0) return '—';
  const index = currentFrameIndex.value;
  if (index < 0) return `— / ${images.value.length}`;
  return `${index + 1} / ${images.value.length}`;
});

const validationLabel = computed(() => {
  if (!currentImage.value) return 'No Image';
  return {
    passed: 'Validated',
    failed: 'Failed',
    not_validated: 'Not Validated',
  }[currentImage.value.validation] ?? 'Not Validated';
});

// Count of labeled frames for Auto Label button (PROP-UI-003)
const labeledFrameCount = computed(() => {
  return images.value.filter(img => img.manually_labeled).length;
});

// Images with mask status for the slider (PROP-UI-004)
const imagesWithMaskStatus = computed(() => {
  return images.value.map(img => ({
    ...img,
    has_mask: maskStatusByFrame.value.get(img.frame_number) ?? false,
  }));
});

// Track which frames have masks (for slider display)
const maskStatusByFrame = ref<Map<number, boolean>>(new Map());

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

function syncSelectedLabel(): void {
  const enabled = enabledLabels.value;
  if (enabled.length === 0) {
    selectedLabel.value = null;
    return;
  }
  if (!selectedLabel.value || !enabled.some(label => label.id === selectedLabel.value?.id)) {
    selectedLabel.value = enabled[0];
  }
}

async function fetchLabels(): Promise<void> {
  try {
    console.log('Fetching project label settings');
    const { data } = await api.get<LabelSetting[]>(
      `/projects/${projectId}/label_settings`,
    );
    console.log('Fetched project labels:', data.length);
    labels.value = data || [];
    syncSelectedLabel();
  } catch (error) {
    console.error('Failed to fetch labels:', error);
    labels.value = [];
    selectedLabel.value = null;
  }
}

async function fetchSettings(): Promise<void> {
  try {
    const { data } = await api.get<{ big_jump_size: number }>('/settings');
    if (data.big_jump_size) {
      bigJumpSize.value = data.big_jump_size;
      console.log('Loaded big_jump_size from config:', bigJumpSize.value);
    }
  } catch (error) {
    console.error('Failed to fetch settings:', error);
    // Keep default value
  }
}

async function setValidationStatus(status: 'passed' | 'failed'): Promise<void> {
  if (!currentImage.value || validationBusy.value) return;
  validationBusy.value = true;
  try {
    const { data } = await api.patch<{ images: ImageData[]; total: number }>(
      `/projects/${projectId}/frames/${currentFrameNumber.value}/validation`,
      { validation: status },
    );
    images.value = data.images || [];
    totalFrames.value = data.total || images.value.length;
    fetchMaskStatus();
  } catch (error) {
    console.error('Failed to update validation status:', error);
  } finally {
    validationBusy.value = false;
  }
}

function selectLabel(label: LabelSetting): void {
  selectedLabel.value = label;
  console.log('Selected label:', label.name);
}

function cycleToNextLabel(): void {
  const enabled = enabledLabels.value;
  if (enabled.length === 0) return;
  
  if (!selectedLabel.value) {
    selectedLabel.value = enabled[0];
    return;
  }
  
  const currentIndex = enabled.findIndex(l => l.id === selectedLabel.value?.id);
  const nextIndex = (currentIndex + 1) % enabled.length;
  selectedLabel.value = enabled[nextIndex];
  console.log('Switched to label:', selectedLabel.value.name);
}

function handleThumbnailError(event: Event): void {
  // Hide broken thumbnail images
  const img = event.target as HTMLImageElement;
  if (img && img.parentElement) {
    img.parentElement.style.display = 'none';
  }
}

// Clear a specific label's points and masks from the current frame
async function clearLabelFromFrame(labelId: string): Promise<void> {
  try {
    await api.delete(
      `/projects/${projectId}/frames/${currentFrameNumber.value}/labels`,
      { params: { label_id: labelId } }
    );
    // Refresh the image viewer to clear the displayed points/masks
    if (imageViewerRef.value) {
      await imageViewerRef.value.refreshPointsAndMasks();
    }
    // Update the images list
    await refreshImagesList();
    // Update mask status for current frame
    await updateCurrentFrameMaskStatus();
  } catch (error) {
    console.error('Failed to clear label from frame:', error);
  }
}

// Clear all labels and masks from the current frame
async function clearAllLabelsFromFrame(): Promise<void> {
  showClearAllConfirm.value = false;
  try {
    await api.delete(`/projects/${projectId}/frames/${currentFrameNumber.value}/labels`);
    // Refresh the image viewer to clear the displayed points/masks
    if (imageViewerRef.value) {
      await imageViewerRef.value.refreshPointsAndMasks();
    }
    // Update the images list
    await refreshImagesList();
    // Update mask status for current frame (should be false after clear all)
    maskStatusByFrame.value.set(currentFrameNumber.value, false);
  } catch (error) {
    console.error('Failed to clear all labels from frame:', error);
  }
}

// Update the mask status for the current frame
async function updateCurrentFrameMaskStatus(): Promise<void> {
  try {
    const response = await api.get(`/projects/${projectId}/frames/${currentFrameNumber.value}/masks`);
    const hasMasks = response.data && response.data.length > 0;
    maskStatusByFrame.value.set(currentFrameNumber.value, hasMasks);
  } catch {
    maskStatusByFrame.value.set(currentFrameNumber.value, false);
  }
}

// Refresh the images list after clearing labels
async function refreshImagesList(): Promise<void> {
  try {
    const { data } = await api.get<{ images: ImageData[]; total: number }>(`/projects/${projectId}/images`);
    images.value = data.images || [];
    totalFrames.value = data.total || 0;
  } catch (error) {
    console.error('Failed to refresh images:', error);
  }
}

function resetView(): void {
  imageViewerRef.value?.resetView();
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
  const currentIndex = images.value.findIndex(img => img.frame_number === currentFrameNumber.value);
  if (currentIndex < 0) return;
  
  // Find the next frame that is manually labeled (after current frame)
  for (let i = currentIndex + 1; i < images.value.length; i++) {
    if (images.value[i].manually_labeled) {
      currentFrameNumber.value = images.value[i].frame_number;
      return;
    }
  }
  
  // No labeled frame found after current position
  console.log('No more labeled frames ahead');
}

function previousLabeledFrame(): void {
  const currentIndex = images.value.findIndex(img => img.frame_number === currentFrameNumber.value);
  if (currentIndex < 0) return;
  
  // Find the previous frame that is manually labeled (before current frame)
  for (let i = currentIndex - 1; i >= 0; i--) {
    if (images.value[i].manually_labeled) {
      currentFrameNumber.value = images.value[i].frame_number;
      return;
    }
  }
  
  // No labeled frame found before current position
  console.log('No more labeled frames behind');
}

function onFrameLabeled(frameNumber: number): void {
  // Update the local images array to mark this frame as labeled
  const image = images.value.find(img => img.frame_number === frameNumber);
  if (image) {
    image.manually_labeled = true;
    console.log('Frame marked as labeled:', frameNumber);
  }
}

function bigJump(): void {
  const currentIndex = images.value.findIndex(img => img.frame_number === currentFrameNumber.value);
  if (currentIndex >= 0) {
    const targetIndex = Math.min(currentIndex + bigJumpSize.value, images.value.length - 1);
    currentFrameNumber.value = images.value[targetIndex].frame_number;
  }
}

// PROP-UI-003: Navigate to propagation page
async function goToPropagation(): Promise<void> {
  if (labeledFrameCount.value === 0) return;
  
  try {
    // Mark propagation stage as visited before navigating
    const { data } = await api.post<Project>(`/projects/${projectId}/mark_stage_visited?stage=propagation`);
    project.value = data;
  } catch (error) {
    console.error('Failed to mark propagation stage as visited:', error);
  }
  
  router.push({ name: 'Propagation', params: { id: projectId } });
}

function handlePrepareAction(): void {
  if (labeledFrameCount.value === 0) return;
  if (isValidationMode.value) {
    router.push({ name: 'Export', params: { id: projectId } });
  } else {
    goToPropagation();
  }
}

// PROP-UI-004: Navigate to frame from slider click
function goToFrameFromSlider(frameNumber: number): void {
  currentFrameNumber.value = frameNumber;
}

// PROP-UI-004: Fetch mask status for all frames (called after initial load and propagation)
async function fetchMaskStatus(): Promise<void> {
  try {
    const { data } = await api.get<{ frames: FrameStatusData[] }>(
      `/projects/${projectId}/frame-statuses`,
    );
    const statusMap = new Map<number, boolean>();
    for (const frame of data.frames || []) {
      statusMap.set(frame.frame_number, frame.has_mask ?? false);
      const image = images.value.find(img => img.frame_number === frame.frame_number);
      if (image) {
        image.manually_labeled = frame.manually_labeled;
        image.validation = frame.validation;
        image.status = frame.status;
      }
    }
    maskStatusByFrame.value = statusMap;
  } catch (error) {
    console.error('Failed to fetch mask status:', error);
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
    case 't':
      cycleToNextLabel();
      break;
    case 'z':
      if (isValidationMode.value) {
        setValidationStatus('passed');
      }
      break;
    case 'x':
      if (isValidationMode.value) {
        setValidationStatus('failed');
      }
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
    if (isValidationMode.value) {
      const validationRes = await api.post<Project>(
        `/projects/${projectId}/mark_stage_visited?stage=validation`,
      );
      if (validationRes.data) {
        project.value = validationRes.data;
      }
      if (project.value?.stage !== 'validation') {
        const stageRes = await api.patch<Project>(
          `/projects/${projectId}`,
          { stage: 'validation' },
        );
        if (stageRes.data) {
          project.value = stageRes.data;
        }
      }
    }
    
    // Load images, labels, and settings from backend
    await Promise.all([fetchImages(), fetchLabels(), fetchSettings()]);
    
    // PROP-UI-004: Fetch mask status for slider display
    // Do this after images are loaded, but don't block the UI
    fetchMaskStatus();
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

watch(enabledLabels, () => {
  syncSelectedLabel();
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
  grid-template-columns: 1fr 420px;
  grid-template-rows: auto 1fr;
  gap: 1.5rem;
  padding: 0;
  width: 100%;
  max-width: 1600px;
  transition: grid-template-columns 0.3s ease;
}

.labeling-container.sidebar-hidden {
  grid-template-columns: 1fr;
  max-width: 100%;
}

/* PROP-UI-004: Slider wrapper spans full width */
.slider-wrapper {
  grid-column: 1 / -1;
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
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  height: fit-content;
  transition: opacity 0.3s ease, transform 0.3s ease;
  align-items: start;
}

.control-column {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  padding: 1.25rem;
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 16px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
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

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border, #e5e7eb);
}

.section-header h3 {
  padding-bottom: 0;
  border-bottom: none;
}

.section-hint {
  font-size: 0.7rem;
  color: var(--muted, #9ca3af);
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.section-hint kbd {
  display: inline-block;
  padding: 0.15rem 0.4rem;
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 0.7rem;
  font-weight: 600;
  color: #2563eb;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
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

.validation-section {
  border-top: 1px solid var(--border, #e5e7eb);
  padding-top: 1rem;
}

.validation-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.7rem 0.85rem;
  background: var(--surface-muted, #f9fafb);
  border-radius: 10px;
  border: 1px solid var(--border, #e5e7eb);
}

.validation-status span {
  font-size: 0.85rem;
  color: var(--muted, #6b7280);
  font-weight: 500;
}

.validation-pill {
  padding: 0.25rem 0.6rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  background: rgba(148, 163, 184, 0.15);
  color: #64748b;
}

.validation-pill[data-status='passed'] {
  background: rgba(34, 197, 94, 0.15);
  color: #16a34a;
}

.validation-pill[data-status='failed'] {
  background: rgba(239, 68, 68, 0.15);
  color: #dc2626;
}

.validation-actions {
  display: flex;
  gap: 0.6rem;
}

.btn-validate {
  flex: 1;
  padding: 0.7rem 0.9rem;
  border-radius: 10px;
  border: 1px solid transparent;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
}

.btn-validate:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-pass {
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.15), rgba(34, 197, 94, 0.05));
  color: #16a34a;
  border-color: rgba(34, 197, 94, 0.35);
}

.btn-pass:hover:not(:disabled) {
  background: linear-gradient(135deg, #16a34a, #22c55e);
  color: #ffffff;
  border-color: transparent;
  transform: translateY(-1px);
}

.btn-fail {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.15), rgba(239, 68, 68, 0.05));
  color: #dc2626;
  border-color: rgba(239, 68, 68, 0.35);
}

.btn-fail:hover:not(:disabled) {
  background: linear-gradient(135deg, #dc2626, #ef4444);
  color: #ffffff;
  border-color: transparent;
  transform: translateY(-1px);
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
  justify-content: space-between;
  padding: 0.5rem 0.75rem;
  background: var(--surface-muted, #f9fafb);
  border: 2px solid var(--border, #e5e7eb);
  border-radius: 10px;
  transition: all 0.2s ease;
}

.label-option:hover {
  background: var(--surface, #ffffff);
  border-color: #2563eb;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15);
}

.label-option.active {
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.1), rgba(124, 58, 237, 0.05));
  border-color: #2563eb;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
}

.label-option-content {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
  cursor: pointer;
}

.btn-clear-label {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: var(--muted, #9ca3af);
  cursor: pointer;
  opacity: 0;
  transition: all 0.15s ease;
}

.label-option:hover .btn-clear-label {
  opacity: 1;
}

.btn-clear-label:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.btn-clear-all {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.6rem 0.75rem;
  margin-top: 0.5rem;
  background: transparent;
  border: 1px dashed var(--border, #e5e7eb);
  border-radius: 8px;
  color: var(--muted, #6b7280);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-clear-all:hover {
  background: rgba(239, 68, 68, 0.05);
  border-color: #ef4444;
  color: #ef4444;
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
  gap: 0.75rem;
}

.mode-key {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  white-space: nowrap;
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

@media (max-width: 1400px) {
  .labeling-container {
    grid-template-columns: 1fr 380px;
  }
}

@media (max-width: 1200px) {
  .labeling-container {
    grid-template-columns: 1fr 340px;
  }
  
  .control-panel {
    grid-template-columns: 1fr;
  }
  
  .control-column:last-child {
    border-top: 1px solid var(--border, #e5e7eb);
    padding-top: 1rem;
  }
}

@media (max-width: 768px) {
  .labeling-container {
    grid-template-columns: 1fr;
  }
  
  .control-panel {
    order: -1;
    grid-template-columns: 1fr;
  }
}

/* PROP-UI-003: Auto Label Section Styles */
.auto-label-section {
  border-top: 1px solid var(--border, #e5e7eb);
  padding-top: 1rem;
}

.section-description {
  margin: 0 0 0.75rem;
  font-size: 0.85rem;
  color: var(--muted, #6b7280);
  line-height: 1.5;
}

.labeled-frames-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 0.9rem;
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.1), rgba(34, 197, 94, 0.05));
  border-radius: 8px;
  margin-bottom: 0.75rem;
  font-size: 0.85rem;
  font-weight: 500;
  color: #16a34a;
}

.labeled-frames-info.warning {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.1), rgba(245, 158, 11, 0.05));
  color: #d97706;
}

.info-icon {
  font-weight: 700;
}

.btn-auto-label {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  padding: 0.9rem 1.2rem;
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 4px 14px rgba(124, 58, 237, 0.25);
}

.btn-auto-label:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(124, 58, 237, 0.35);
}

.btn-auto-label:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: var(--surface-muted, #9ca3af);
  box-shadow: none;
}

.btn-auto-label--export {
  background: linear-gradient(135deg, #0ea5e9, #2563eb);
  box-shadow: 0 4px 14px rgba(14, 165, 233, 0.25);
}

.btn-auto-label--export:hover:not(:disabled) {
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.35);
}

.btn-auto-label svg {
  flex-shrink: 0;
}

/* Clear All Confirmation Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  animation: fadeIn 0.15s ease;
}

.modal-dialog {
  background: var(--surface, #ffffff);
  border-radius: 16px;
  padding: 1.5rem;
  max-width: 400px;
  width: 90%;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  animation: slideUp 0.2s ease;
}

.modal-dialog h3 {
  margin: 0 0 0.75rem;
  font-size: 1.1rem;
  color: var(--text, #0f172a);
}

.modal-dialog p {
  margin: 0 0 1.25rem;
  font-size: 0.9rem;
  color: var(--muted, #6b7280);
  line-height: 1.5;
}

.modal-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
}

.btn-cancel {
  padding: 0.6rem 1rem;
  background: var(--surface-muted, #f3f4f6);
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 8px;
  color: var(--text, #374151);
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-cancel:hover {
  background: var(--surface, #ffffff);
  border-color: var(--border-hover, #d1d5db);
}

.btn-confirm-delete {
  padding: 0.6rem 1rem;
  background: #ef4444;
  border: none;
  border-radius: 8px;
  color: #ffffff;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-confirm-delete:hover {
  background: #dc2626;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
