<template>
  <div class="image-viewer" ref="containerRef">
    <v-stage
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
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
  cursor: default;
}

.image-viewer canvas {
  display: block;
}
</style>
