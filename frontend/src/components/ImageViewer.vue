<template>
  <div class="image-viewer" ref="containerRef">
    <v-stage
      v-if="imageElement"
      ref="stageRef"
      :config="stageConfig"
      @mousedown="handleMouseDown"
      @mousemove="handleMouseMove"
      @mouseup="handleMouseUp"
      @wheel="handleWheel"
      @contextmenu.prevent
    >
      <v-layer>
        <v-image
          :config="imageConfig"
        />
      </v-layer>
    </v-stage>
    
    <!-- Placeholder when no image is loaded -->
    <div v-else class="placeholder">
      <div class="placeholder-content">
        <svg class="placeholder-icon" viewBox="0 0 24 24" width="48" height="48">
          <path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z" fill="currentColor"/>
        </svg>
        <p class="placeholder-text">No image loaded</p>
        <p class="placeholder-subtext">Images will appear here when available</p>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import Konva from 'konva';

interface Props {
  imageUrl: string;
  width?: number;
  height?: number;
}

const props = withDefaults(defineProps<Props>(), {
  width: 1200,
  height: 800,
});

const containerRef = ref<HTMLElement | null>(null);
const stageRef = ref<any>(null);
const imageElement = ref<HTMLImageElement | null>(null);
const imageLoaded = ref(false);

// Pan and zoom state
const scale = ref(1);
const position = ref({ x: 0, y: 0 });
const isDragging = ref(false);
const lastPointerPosition = ref({ x: 0, y: 0 });

// Image dimensions
const imageWidth = ref(0);
const imageHeight = ref(0);

const stageConfig = computed(() => ({
  width: props.width,
  height: props.height,
  draggable: false,
  scaleX: scale.value,
  scaleY: scale.value,
  x: position.value.x,
  y: position.value.y,
}));

const imageConfig = computed(() => ({
  image: imageElement.value,
  x: 0,
  y: 0,
  width: imageWidth.value,
  height: imageHeight.value,
}));

function loadImage(url: string): void {
  const img = new Image();
  img.crossOrigin = 'anonymous';
  
  img.onload = () => {
    imageElement.value = img;
    imageWidth.value = img.width;
    imageHeight.value = img.height;
    imageLoaded.value = true;
    
    // Center the image initially
    resetView();
  };
  
  img.onerror = (error) => {
    console.error('Failed to load image:', error);
  };
  
  img.src = url;
}

function resetView(): void {
  if (!imageElement.value) return;
  
  // Calculate scale to fit image in viewport
  const scaleX = props.width / imageWidth.value;
  const scaleY = props.height / imageHeight.value;
  const fitScale = Math.min(scaleX, scaleY, 1); // Don't scale up beyond 100%
  
  scale.value = fitScale;
  
  // Center the image
  const scaledWidth = imageWidth.value * fitScale;
  const scaledHeight = imageHeight.value * fitScale;
  position.value = {
    x: (props.width - scaledWidth) / 2,
    y: (props.height - scaledHeight) / 2,
  };
}

function handleMouseDown(e: any): void {
  const evt = e.evt as MouseEvent;
  
  // Only handle right mouse button for panning
  if (evt.button === 2) {
    isDragging.value = true;
    lastPointerPosition.value = {
      x: evt.clientX,
      y: evt.clientY,
    };
    
    // Change cursor
    if (containerRef.value) {
      containerRef.value.style.cursor = 'grabbing';
    }
  }
}

function handleMouseMove(e: any): void {
  if (!isDragging.value) return;
  
  const evt = e.evt as MouseEvent;
  const dx = evt.clientX - lastPointerPosition.value.x;
  const dy = evt.clientY - lastPointerPosition.value.y;
  
  position.value = {
    x: position.value.x + dx,
    y: position.value.y + dy,
  };
  
  lastPointerPosition.value = {
    x: evt.clientX,
    y: evt.clientY,
  };
}

function handleMouseUp(e: any): void {
  const evt = e.evt as MouseEvent;
  
  if (evt.button === 2) {
    isDragging.value = false;
    
    // Reset cursor
    if (containerRef.value) {
      containerRef.value.style.cursor = 'default';
    }
  }
}

function handleWheel(e: any): void {
  e.evt.preventDefault();
  
  const evt = e.evt as WheelEvent;
  const stage = stageRef.value?.getStage();
  if (!stage) return;
  
  const oldScale = scale.value;
  const pointer = stage.getPointerPosition();
  
  if (!pointer) return;
  
  // Zoom factor
  const scaleBy = 1.05;
  const direction = evt.deltaY > 0 ? -1 : 1;
  
  // Calculate new scale
  let newScale = direction > 0 ? oldScale * scaleBy : oldScale / scaleBy;
  
  // Limit zoom range
  newScale = Math.max(0.1, Math.min(newScale, 10));
  
  // Calculate new position to zoom towards pointer
  const mousePointTo = {
    x: (pointer.x - position.value.x) / oldScale,
    y: (pointer.y - position.value.y) / oldScale,
  };
  
  const newPos = {
    x: pointer.x - mousePointTo.x * newScale,
    y: pointer.y - mousePointTo.y * newScale,
  };
  
  scale.value = newScale;
  position.value = newPos;
}

// Watch for image URL changes
watch(() => props.imageUrl, (newUrl) => {
  if (newUrl) {
    imageLoaded.value = false;
    loadImage(newUrl);
  }
}, { immediate: true });

// Expose reset view function
defineExpose({
  resetView,
});

onMounted(() => {
  // Set up keyboard listener for R key
  const handleKeyPress = (e: KeyboardEvent) => {
    if (e.key === 'r' || e.key === 'R') {
      // Check if not typing in input
      if (!(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement)) {
        resetView();
      }
    }
  };
  
  window.addEventListener('keydown', handleKeyPress);
  
  return () => {
    window.removeEventListener('keydown', handleKeyPress);
  };
});
</script>

<style scoped>
.image-viewer {
  position: relative;
  background: #1a1a1a;
  border: 1px solid #dfe3ec;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
  height: 700px;
}

.image-viewer canvas {
  display: block;
}

.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #f3f4f6, #eef2f7);
  border: 2px dashed #dfe3ec;
  border-radius: 16px;
}

.placeholder-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  text-align: center;
}

.placeholder-icon {
  color: #d1d5db;
  opacity: 0.6;
}

.placeholder-text {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #6b7280;
}

.placeholder-subtext {
  margin: 0;
  font-size: 0.875rem;
  color: #9ca3af;
}
</style>
