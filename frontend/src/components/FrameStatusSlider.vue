<template>
  <div class="frame-status-slider" ref="containerRef">
    <div class="slider-header">
      <span class="slider-label">Frame Progress</span>
      <span class="slider-info">{{ currentIndexLabel }}</span>
    </div>
    
    <div class="slider-track" @click="handleTrackClick" @mousemove="handleTrackHover" @mouseleave="hoveredFrame = null">
      <!-- Segment blocks for each frame status -->
      <div 
        v-for="segment in segments" 
        :key="segment.startFrame"
        class="segment"
        :class="segment.status"
        :style="{ 
          left: `${segmentPosition(segment.startFrame)}%`,
          width: `${segmentWidth(segment.startFrame, segment.endFrame)}%`
        }"
        :title="getSegmentTooltip(segment)"
      ></div>
      
      <!-- Current position indicator -->
      <div 
        class="position-indicator"
        :style="{ left: `${currentPosition}%` }"
      ></div>
      
      <!-- Hover tooltip -->
      <div 
        v-if="hoveredFrame !== null" 
        class="hover-tooltip"
        :style="{ left: `${framePosition(hoveredFrame)}%` }"
      >
        Frame {{ hoveredFrame }}
        <span class="tooltip-status">{{ getFrameStatusLabel(hoveredFrame) }}</span>
      </div>
    </div>
    
    <div class="legend">
      <div class="legend-item">
        <span class="legend-dot manual"></span>
        <span class="legend-label">Manual ({{ manualCount }})</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot propagated"></span>
        <span class="legend-label">Propagated ({{ propagatedCount }})</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot validated"></span>
        <span class="legend-label">Validated ({{ validatedCount }})</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot failed"></span>
        <span class="legend-label">Failed ({{ failedCount }})</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot unlabeled"></span>
        <span class="legend-label">Unlabeled ({{ unlabeledCount }})</span>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, watch } from 'vue';

interface ImageData {
  id: string;
  frame_number: number;
  status: string;
  manually_labeled: boolean;
  validation: string;
  has_mask?: boolean;
}

interface Segment {
  startFrame: number;
  endFrame: number;
  status: 'manual' | 'propagated' | 'validated' | 'failed' | 'unlabeled';
}

interface Props {
  images: ImageData[];
  currentFrame: number;
  totalFrames: number;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  (e: 'frame-click', frame: number): void;
}>();

const containerRef = ref<HTMLElement | null>(null);
const hoveredFrame = ref<number | null>(null);

const sortedFrames = computed(() =>
  [...props.images].map((img) => img.frame_number).sort((a, b) => a - b),
);

const minFrame = computed(() => sortedFrames.value[0] ?? 0);
const maxFrame = computed(() => sortedFrames.value[sortedFrames.value.length - 1] ?? 0);

const currentIndex = computed(() => {
  const index = sortedFrames.value.indexOf(props.currentFrame);
  return index === -1 ? 0 : index;
});

const currentIndexLabel = computed(() => {
  if (sortedFrames.value.length === 0) return '—';
  return `${currentIndex.value + 1} / ${sortedFrames.value.length}`;
});

const frameRange = computed(() => Math.max(1, maxFrame.value - minFrame.value));

function framePosition(frame: number | null): number {
  if (frame === null) return 0;
  return ((frame - minFrame.value) / frameRange.value) * 100;
}

const currentPosition = computed(() => framePosition(props.currentFrame));

function segmentPosition(startFrame: number): number {
  return framePosition(startFrame);
}

function segmentWidth(startFrame: number, endFrame: number): number {
  return ((endFrame - startFrame + 1) / (frameRange.value + 1)) * 100;
}

// Compute frame statuses
const frameStatuses = computed(() => {
  const statuses = new Map<number, 'manual' | 'propagated' | 'validated' | 'failed' | 'unlabeled'>();
  
  for (const img of props.images) {
    let status: 'manual' | 'propagated' | 'validated' | 'failed' | 'unlabeled';
    
    if (img.validation === 'passed') {
      status = 'validated';
    } else if (img.validation === 'failed') {
      status = 'failed';
    } else if (img.manually_labeled) {
      status = 'manual';
    } else if (img.has_mask) {
      status = 'propagated';
    } else {
      status = 'unlabeled';
    }
    
    statuses.set(img.frame_number, status);
  }
  
  return statuses;
});

// Convert to segments for efficient rendering
const segments = computed<Segment[]>(() => {
  if (props.images.length === 0) return [];
  
  const sortedFrames = [...props.images].sort((a, b) => a.frame_number - b.frame_number);
  const result: Segment[] = [];
  
  let currentSegment: Segment | null = null;
  
  for (const img of sortedFrames) {
    const status = frameStatuses.value.get(img.frame_number) || 'unlabeled';
    
    if (!currentSegment || currentSegment.status !== status || img.frame_number !== currentSegment.endFrame + 1) {
      // Start new segment
      if (currentSegment) {
        result.push(currentSegment);
      }
      currentSegment = {
        startFrame: img.frame_number,
        endFrame: img.frame_number,
        status,
      };
    } else {
      // Extend current segment
      currentSegment.endFrame = img.frame_number;
    }
  }
  
  if (currentSegment) {
    result.push(currentSegment);
  }
  
  return result;
});

// Count statistics
const manualCount = computed(() => 
  props.images.filter(
    img => img.manually_labeled && img.validation !== 'passed' && img.validation !== 'failed',
  ).length
);

const propagatedCount = computed(() => 
  props.images.filter(
    img => !img.manually_labeled && img.has_mask && img.validation !== 'passed' && img.validation !== 'failed',
  ).length
);

const validatedCount = computed(() => 
  props.images.filter(img => img.validation === 'passed').length
);

const failedCount = computed(() => 
  props.images.filter(img => img.validation === 'failed').length
);

const unlabeledCount = computed(() => 
  props.images.filter(
    img => !img.manually_labeled && !img.has_mask && img.validation !== 'passed' && img.validation !== 'failed',
  ).length
);

function getSegmentTooltip(segment: Segment): string {
  const count = segment.endFrame - segment.startFrame + 1;
  const statusLabel = {
    manual: 'Manually Labeled',
    propagated: 'Propagated',
    validated: 'Validated',
    failed: 'Failed Validation',
    unlabeled: 'Unlabeled',
  }[segment.status];
  
  if (count === 1) {
    return `Frame ${segment.startFrame}: ${statusLabel}`;
  }
  return `Frames ${segment.startFrame}-${segment.endFrame}: ${statusLabel} (${count} frames)`;
}

function getFrameStatusLabel(frameNumber: number): string {
  const status = frameStatuses.value.get(frameNumber);
  return {
    manual: 'Manually Labeled',
    propagated: 'Propagated',
    validated: 'Validated',
    failed: 'Failed',
    unlabeled: 'Unlabeled',
  }[status || 'unlabeled'];
}

function handleTrackClick(event: MouseEvent): void {
  if (!containerRef.value) return;
  
  const track = (event.currentTarget as HTMLElement);
  const rect = track.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const percentage = x / rect.width;
  const targetFrame = Math.round(minFrame.value + percentage * frameRange.value);
  
  // Find closest valid frame
  const validFrames = sortedFrames.value;
  const closestFrame = validFrames.reduce((prev, curr) => 
    Math.abs(curr - targetFrame) < Math.abs(prev - targetFrame) ? curr : prev
  );
  
  emit('frame-click', closestFrame);
}

function handleTrackHover(event: MouseEvent): void {
  const track = (event.currentTarget as HTMLElement);
  const rect = track.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const percentage = x / rect.width;
  const targetFrame = Math.round(minFrame.value + percentage * frameRange.value);
  
  // Find closest valid frame
  const validFrames = sortedFrames.value;
  if (validFrames.length === 0) {
    hoveredFrame.value = null;
    return;
  }
  
  hoveredFrame.value = validFrames.reduce((prev, curr) => 
    Math.abs(curr - targetFrame) < Math.abs(prev - targetFrame) ? curr : prev
  );
}
</script>

<style scoped>
.frame-status-slider {
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 12px;
  padding: 1rem;
  margin-bottom: 1rem;
}

.slider-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.slider-label {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text, #0f172a);
}

.slider-info {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--muted, #6b7280);
}

.slider-track {
  position: relative;
  height: 24px;
  background: var(--surface-muted, #f3f4f6);
  border-radius: 6px;
  cursor: pointer;
  overflow: hidden;
}

.segment {
  position: absolute;
  top: 0;
  height: 100%;
  transition: opacity 0.2s ease;
}

.segment:hover {
  opacity: 0.8;
}

.segment.manual {
  background: linear-gradient(135deg, #2563eb, #3b82f6);
  min-width: 2px;
}

.segment.propagated {
  background: linear-gradient(135deg, #7c3aed, #8b5cf6);
}

.segment.validated {
  background: linear-gradient(135deg, #22c55e, #4ade80);
}

.segment.failed {
  background: linear-gradient(135deg, #ef4444, #f87171);
}

.segment.unlabeled {
  background: var(--surface-muted, #e5e7eb);
}

.position-indicator {
  position: absolute;
  top: -4px;
  bottom: -4px;
  width: 3px;
  background: var(--text, #0f172a);
  border-radius: 2px;
  transform: translateX(-50%);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  pointer-events: none;
  z-index: 10;
}

.position-indicator::before {
  content: '';
  position: absolute;
  top: -6px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 6px solid var(--text, #0f172a);
}

.hover-tooltip {
  position: absolute;
  bottom: calc(100% + 8px);
  transform: translateX(-50%);
  background: var(--text, #0f172a);
  color: white;
  padding: 0.4rem 0.6rem;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  white-space: nowrap;
  pointer-events: none;
  z-index: 20;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.2rem;
}

.hover-tooltip::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 5px solid var(--text, #0f172a);
}

.tooltip-status {
  font-size: 0.65rem;
  font-weight: 500;
  opacity: 0.8;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border, #e5e7eb);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
}

.legend-dot.manual {
  background: #2563eb;
}

.legend-dot.propagated {
  background: #7c3aed;
}

.legend-dot.validated {
  background: #22c55e;
}

.legend-dot.failed {
  background: #ef4444;
}

.legend-dot.unlabeled {
  background: #e5e7eb;
}

.legend-label {
  font-size: 0.75rem;
  color: var(--muted, #6b7280);
  font-weight: 500;
}
</style>

