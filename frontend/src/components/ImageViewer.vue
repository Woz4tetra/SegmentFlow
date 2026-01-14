<template>
  <div class="image-viewer" ref="containerRef" @contextmenu.prevent>
    <canvas 
      v-if="imageLoaded"
      ref="canvasRef"
      :width="width"
      :height="height"
      class="fabric-canvas"
      @contextmenu.prevent
    />
    
    <!-- Placeholder when no image is loaded -->
    <div v-else class="placeholder">
      <div class="placeholder-content">
        <img 
          class="placeholder-icon" 
          src="/image_256dp_FFFFFF_FILL0_wght400_GRAD0_opsz48.svg" 
          alt="No image" 
          width="48" 
          height="48"
        />
        <p class="placeholder-text">No image loaded</p>
        <p class="placeholder-subtext">Images will appear here when available</p>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted, watch, onBeforeUnmount, nextTick } from 'vue';
import { fabric } from 'fabric';

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
const canvasRef = ref<HTMLCanvasElement | null>(null);
let fabricCanvas: fabric.Canvas | null = null;
let fabricImg: fabric.Image | null = null; // Store reference to the image object

const imageLoaded = ref(false);

// Pan and zoom state
const scale = ref(1);
const position = ref({ x: 0, y: 0 });
const isDragging = ref(false);
const lastPointerPosition = ref({ x: 0, y: 0 });

// Store window event listeners for cleanup
let windowMouseMoveHandler: ((e: MouseEvent) => void) | null = null;
let windowMouseUpHandler: ((e: MouseEvent) => void) | null = null;

// Image dimensions
const imageWidth = ref(0);
const imageHeight = ref(0);

function loadImage(url: string): void {
  const img = new Image();
  img.crossOrigin = 'anonymous';
  
  img.onload = () => {
    imageWidth.value = img.width;
    imageHeight.value = img.height;
    imageLoaded.value = true;
    
    // Initialize canvas on next tick to ensure DOM is ready
    nextTick(() => {
      if (canvasRef.value) {
        // Dispose old canvas if it exists
        if (fabricCanvas) {
          try {
            fabricCanvas.dispose();
          } catch (e) {
            console.warn('Error disposing canvas:', e);
          }
          fabricCanvas = null;
          fabricImg = null;
        }
        initializeFabricCanvas(img);
      }
    });
  };
  
  img.onerror = (error) => {
    console.error('Failed to load image:', error);
  };
  
  img.src = url;
}

function initializeFabricCanvas(img: HTMLImageElement): void {
  if (!canvasRef.value) return;
  
  // Dispose old canvas if it exists
  if (fabricCanvas) {
    fabricCanvas.dispose();
    fabricImg = null;
  }
  
  // Create fabric canvas
  fabricCanvas = new fabric.Canvas(canvasRef.value, {
    width: props.width,
    height: props.height,
    backgroundColor: '#1a1a1a',
    selection: false, // Disable selection
    preserveObjectStacking: true,
  });
  
  // Create fabric image from HTMLImageElement
  fabricImg = new fabric.Image(img, {
    left: 0,
    top: 0,
    selectable: false, // Disable selection handles
    evented: false, // Disable interaction with the image itself
    hoverCursor: 'default',
    moveCursor: 'default',
  });
  
  fabricCanvas.add(fabricImg);
  fabricCanvas.renderAll();
  
  // Center the image initially
  resetView();
  
  // Set up event handlers
  setupEventHandlers();
}

function resetView(): void {
  if (!fabricCanvas || !fabricImg) return;
  
  // Ensure no objects are selected
  fabricCanvas.discardActiveObject();
  
  // Calculate scale to fit image in viewport
  const scaleX = props.width / imageWidth.value;
  const scaleY = props.height / imageHeight.value;
  const fitScale = Math.min(scaleX, scaleY, 1); // Don't scale up beyond 100%
  
  scale.value = fitScale;
  
  // Set the image scale
  fabricImg.set({
    scaleX: fitScale,
    scaleY: fitScale,
  });
  
  // Center the image
  const scaledWidth = imageWidth.value * fitScale;
  const scaledHeight = imageHeight.value * fitScale;
  const centerX = (props.width - scaledWidth) / 2;
  const centerY = (props.height - scaledHeight) / 2;
  
  fabricImg.set({
    left: centerX,
    top: centerY,
  });
  
  fabricCanvas.renderAll();
}

function setupEventHandlers(): void {
  if (!fabricCanvas) return;
  
  // Disable all default Fabric.js interactions
  fabricCanvas.on('selection:created', (e: any) => {
    e.e?.stopPropagation();
    fabricCanvas?.discardActiveObject();
  });
  fabricCanvas.on('selection:updated', (e: any) => {
    e.e?.stopPropagation();
    fabricCanvas?.discardActiveObject();
  });
  
  const container = containerRef.value;
  if (!container) return;
  
  // Prevent context menu on container
  container.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    e.stopPropagation();
    return false;
  });
  
  // Attach mousedown to container - right mouse button only
  container.addEventListener('mousedown', (e) => {
    if (e.button === 2) {
      // Right click - prevent context menu and handle panning
      e.preventDefault();
      e.stopPropagation();
      handleMouseDown(e);
    }
  });
  
  // Also attach to the canvas element itself
  const canvas = fabricCanvas.lowerCanvasEl as HTMLCanvasElement;
  if (canvas) {
    canvas.addEventListener('mousedown', (e) => {
      if (e.button === 2) {
        e.preventDefault();
        e.stopPropagation();
        handleMouseDown(e);
      }
    });
  }
  
  // Attach wheel to container
  container.addEventListener('wheel', handleWheel, { passive: false });
}

function handleMouseDown(e: MouseEvent): void {
  isDragging.value = true;
  lastPointerPosition.value = {
    x: e.clientX,
    y: e.clientY,
  };
  
  // Change cursor
  if (containerRef.value) {
    containerRef.value.style.cursor = 'grabbing';
  }
  
  // Attach window-level event listeners for dragging
  windowMouseMoveHandler = handleMouseMove;
  windowMouseUpHandler = handleMouseUp;
  window.addEventListener('mousemove', windowMouseMoveHandler, { passive: false });
  window.addEventListener('mouseup', windowMouseUpHandler, { passive: false });
}

function handleMouseMove(e: MouseEvent): void {
  if (!isDragging.value || !fabricCanvas || !fabricImg) {
    return;
  }
  
  e.preventDefault();
  e.stopPropagation();
  
  const dx = e.clientX - lastPointerPosition.value.x;
  const dy = e.clientY - lastPointerPosition.value.y;
  
  // Only pan if there's actual movement
  if (Math.abs(dx) < 0.1 && Math.abs(dy) < 0.1) {
    return;
  }
  
  // Move the image object directly
  const currentLeft = fabricImg.left || 0;
  const currentTop = fabricImg.top || 0;
  
  fabricImg.set({
    left: currentLeft + dx,
    top: currentTop + dy,
  });
  
  fabricCanvas.renderAll();
  
  lastPointerPosition.value = {
    x: e.clientX,
    y: e.clientY,
  };
}

function handleMouseUp(e: MouseEvent): void {
  // Stop dragging on any mouse button release if we're currently dragging
  if (isDragging.value) {
    isDragging.value = false;
    
    // Reset cursor
    if (containerRef.value) {
      containerRef.value.style.cursor = 'default';
    }
    
    // Remove window-level event listeners
    if (windowMouseMoveHandler) {
      window.removeEventListener('mousemove', windowMouseMoveHandler);
      windowMouseMoveHandler = null;
    }
    if (windowMouseUpHandler) {
      window.removeEventListener('mouseup', windowMouseUpHandler);
      windowMouseUpHandler = null;
    }
  }
}

function handleWheel(e: WheelEvent): void {
  if (!fabricCanvas || !fabricImg) return;
  
  e.preventDefault();
  
  const oldScale = scale.value;
  const rect = (fabricCanvas.lowerCanvasEl as HTMLCanvasElement).getBoundingClientRect();
  const pointer = {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
  };
  
  // Zoom factor
  const scaleBy = 1.05;
  const direction = e.deltaY > 0 ? -1 : 1;
  
  // Calculate new scale
  let newScale = direction > 0 ? oldScale * scaleBy : oldScale / scaleBy;
  
  // Limit zoom range
  newScale = Math.max(0.1, Math.min(newScale, 10));
  
  // Get current image position and scale
  const imgLeft = fabricImg.left || 0;
  const imgTop = fabricImg.top || 0;
  const imgScaleX = fabricImg.scaleX || 1;
  
  // Calculate the point in image coordinates (before zoom)
  const imgX = (pointer.x - imgLeft) / imgScaleX;
  const imgY = (pointer.y - imgTop) / imgScaleX;
  
  // Apply new scale
  fabricImg.set({
    scaleX: newScale,
    scaleY: newScale,
  });
  
  // Adjust position to zoom towards the mouse pointer
  const newLeft = pointer.x - imgX * newScale;
  const newTop = pointer.y - imgY * newScale;
  
  fabricImg.set({
    left: newLeft,
    top: newTop,
  });
  
  fabricCanvas.renderAll();
  
  scale.value = newScale;
}

// Watch for image URL changes
watch(() => props.imageUrl, (newUrl) => {
  if (newUrl) {
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

onBeforeUnmount(() => {
  // Clean up window event listeners
  if (windowMouseMoveHandler) {
    window.removeEventListener('mousemove', windowMouseMoveHandler);
    windowMouseMoveHandler = null;
  }
  if (windowMouseUpHandler) {
    window.removeEventListener('mouseup', windowMouseUpHandler);
    windowMouseUpHandler = null;
  }
  
  if (fabricCanvas) {
    try {
      fabricCanvas.dispose();
    } catch (e) {
      console.warn('Error disposing canvas on unmount:', e);
    }
    fabricCanvas = null;
    fabricImg = null;
  }
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
  width: 100%;
  height: 100%;
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
  filter: brightness(0) saturate(100%) invert(91%) sepia(6%) saturate(160%) hue-rotate(182deg) brightness(93%) contrast(87%);
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
