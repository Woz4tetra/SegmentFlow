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
  projectId?: string;
  frameNumber?: number;
  selectedLabelId?: string;
  selectedLabelColor?: string;
}

const props = withDefaults(defineProps<Props>(), {
  width: 1200,
  height: 800,
  projectId: '',
  frameNumber: 0,
  selectedLabelId: '',
  selectedLabelColor: '#2563eb',
});

interface Point {
  x: number;
  y: number;
  include: boolean; // true = include (1), false = exclude (0)
  id: string;
}

interface MaskData {
  rle: string;
  bbox: number[];
}

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

// Point clicking state (CANVAS-003)
const includeMode = ref(true); // true = include (I key), false = exclude (U key)
const points = ref<Point[]>([]); // Store clicked points
const currentMask = ref<MaskData | null>(null); // Current SAM mask
let maskOverlay: fabric.Image | null = null; // Fabric image for mask overlay

// WebSocket connection (SAM-003)
let websocket: WebSocket | null = null;
const wsConnected = ref(false);
const pendingRequests = new Map<string, { resolve: (mask: MaskData | null) => void; reject: (error: any) => void }>();

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
  
  // Attach mousedown to container
  container.addEventListener('mousedown', (e) => {
    if (e.button === 2) {
      // Right click - prevent context menu and handle panning
      e.preventDefault();
      e.stopPropagation();
      handleMouseDown(e);
    } else if (e.button === 0) {
      // Left click - add point for SAM inference
      e.preventDefault();
      e.stopPropagation();
      handleLeftClick(e);
    }
  });
  
  // Also attach to the canvas element itself
  if (canvasRef.value) {
    canvasRef.value.addEventListener('mousedown', (e) => {
      if (e.button === 2) {
        e.preventDefault();
        e.stopPropagation();
        handleMouseDown(e);
      } else if (e.button === 0) {
        e.preventDefault();
        e.stopPropagation();
        handleLeftClick(e);
      }
    });
  }
  
  // Set initial cursor
  container.style.cursor = includeMode.value ? 'crosshair' : 'not-allowed';
  
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
  const rect = containerRef.value!.getBoundingClientRect();
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

function handleLeftClick(e: MouseEvent): void {
  if (!fabricCanvas || !fabricImg || !props.projectId || !props.selectedLabelId) {
    console.warn('Cannot add point: missing required data');
    return;
  }

  // Get click position relative to canvas
  const rect = containerRef.value!.getBoundingClientRect();
  const canvasX = e.clientX - rect.left;
  const canvasY = e.clientY - rect.top;

  // Convert canvas coordinates to image coordinates
  const imgLeft = fabricImg.left || 0;
  const imgTop = fabricImg.top || 0;
  const imgScaleX = fabricImg.scaleX || 1;

  const imgX = (canvasX - imgLeft) / imgScaleX;
  const imgY = (canvasY - imgTop) / imgScaleX;

  // Normalize to [0, 1] range for SAM
  const normalizedX = imgX / imageWidth.value;
  const normalizedY = imgY / imageHeight.value;

  // Validate coordinates are within image bounds
  if (normalizedX < 0 || normalizedX > 1 || normalizedY < 0 || normalizedY > 1) {
    console.warn('Click outside image bounds');
    return;
  }

  // Add point
  const point: Point = {
    x: normalizedX,
    y: normalizedY,
    include: includeMode.value,
    id: `${Date.now()}-${Math.random()}`,
  };

  points.value.push(point);
  console.log('Added point:', point);

  // Render point visual
  renderPoint(point, canvasX, canvasY);

  // Send to SAM for inference
  requestSAMInference();
}

function renderPoint(point: Point, canvasX: number, canvasY: number): void {
  if (!fabricCanvas) return;

  const color = point.include ? props.selectedLabelColor : '#ef4444'; // Red for exclude
  const radius = 6;

  // Create circle for the point
  const circle = new fabric.Circle({
    left: canvasX - radius,
    top: canvasY - radius,
    radius: radius,
    fill: color,
    stroke: '#ffffff',
    strokeWidth: 2,
    selectable: false,
    evented: false,
    shadow: new fabric.Shadow({
      color: 'rgba(0, 0, 0, 0.3)',
      blur: 4,
      offsetX: 0,
      offsetY: 2,
    }),
  });

  fabricCanvas.add(circle);
  fabricCanvas.bringToFront(circle);
  fabricCanvas.renderAll();
}

async function requestSAMInference(): Promise<void> {
  if (!websocket || websocket.readyState !== WebSocket.OPEN) {
    console.error('WebSocket not connected');
    return;
  }

  if (points.value.length === 0) {
    console.warn('No points to send');
    return;
  }

  const requestId = `req-${Date.now()}-${Math.random()}`;

  const request = {
    project_id: props.projectId,
    frame_number: props.frameNumber,
    label_id: props.selectedLabelId,
    points: points.value.map(p => [p.x, p.y]),
    labels: points.value.map(p => (p.include ? 1 : 0)),
    request_id: requestId,
  };

  console.log('Sending SAM request:', request);

  try {
    websocket.send(JSON.stringify(request));
  } catch (error) {
    console.error('Error sending SAM request:', error);
  }
}

function decodeRLE(rle: string, width: number, height: number): Uint8ClampedArray {
  // Decode run-length encoding to binary mask
  const mask = new Uint8ClampedArray(width * height);
  
  if (!rle || rle.length === 0) {
    return mask;
  }

  const pairs = rle.split(';');
  
  for (const pair of pairs) {
    const [startStr, lengthStr] = pair.split(',');
    const start = parseInt(startStr, 10);
    const length = parseInt(lengthStr, 10);
    
    if (isNaN(start) || isNaN(length)) continue;
    
    for (let i = 0; i < length; i++) {
      const idx = start + i;
      if (idx < mask.length) {
        mask[idx] = 255;
      }
    }
  }
  
  return mask;
}

function renderMask(): void {
  if (!fabricCanvas || !currentMask.value || !fabricImg) {
    return;
  }

  // Remove old mask overlay if exists
  if (maskOverlay) {
    fabricCanvas.remove(maskOverlay);
    maskOverlay = null;
  }

  const width = imageWidth.value;
  const height = imageHeight.value;

  // Decode RLE to binary mask
  const maskData = decodeRLE(currentMask.value.rle, width, height);

  // Create RGBA image data for the mask overlay
  const imageData = new ImageData(width, height);
  const color = hexToRgb(props.selectedLabelColor);

  for (let i = 0; i < maskData.length; i++) {
    const alpha = maskData[i];
    if (alpha > 0) {
      const pixelIdx = i * 4;
      imageData.data[pixelIdx] = color.r;
      imageData.data[pixelIdx + 1] = color.g;
      imageData.data[pixelIdx + 2] = color.b;
      imageData.data[pixelIdx + 3] = 128; // 50% transparency
    }
  }

  // Create temporary canvas to hold the mask
  const tempCanvas = document.createElement('canvas');
  tempCanvas.width = width;
  tempCanvas.height = height;
  const ctx = tempCanvas.getContext('2d');
  if (!ctx) return;

  ctx.putImageData(imageData, 0, 0);

  // Create fabric image from the mask canvas
  maskOverlay = new fabric.Image(tempCanvas, {
    left: fabricImg.left,
    top: fabricImg.top,
    scaleX: fabricImg.scaleX,
    scaleY: fabricImg.scaleY,
    selectable: false,
    evented: false,
    opacity: 0.5,
  });

  fabricCanvas.add(maskOverlay);
  // Ensure mask is above image but below points
  fabricCanvas.moveTo(maskOverlay, 1);
  fabricCanvas.renderAll();

  console.log('Rendered mask overlay');
}

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  // Remove # if present
  hex = hex.replace('#', '');
  
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);
  
  return { r, g, b };
}

// Watch for image URL changes
watch(() => props.imageUrl, (newUrl) => {
  if (newUrl) {
    loadImage(newUrl);
    // Clear points when image changes
    points.value = [];
    currentMask.value = null;
    if (maskOverlay && fabricCanvas) {
      fabricCanvas.remove(maskOverlay);
      maskOverlay = null;
    }
  }
}, { immediate: true });

// Expose reset view function and points
defineExpose({
  resetView,
  getPoints: () => points.value,
  clearPoints: () => {
    points.value = [];
    currentMask.value = null;
    if (maskOverlay && fabricCanvas) {
      fabricCanvas.remove(maskOverlay);
      maskOverlay = null;
      fabricCanvas.renderAll();
    }
  },
});

function connectWebSocket(): void {
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    return; // Already connected
  }

  const wsUrl = `ws://localhost:8000/api/v1/sam3/inference`;
  console.log('Connecting to SAM WebSocket:', wsUrl);

  websocket = new WebSocket(wsUrl);

  websocket.onopen = () => {
    console.log('SAM WebSocket connected');
    wsConnected.value = true;
  };

  websocket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      console.log('Received SAM response:', data);

      // Handle queue status updates
      if (data.queue_size !== undefined) {
        console.log(`Queue status: ${data.queue_size} requests pending`);
        return;
      }

      // Handle mask responses
      if (data.status === 'success' && data.mask_rle) {
        currentMask.value = {
          rle: data.mask_rle,
          bbox: data.mask_bbox || [0, 0, 0, 0],
        };
        renderMask();

        // Resolve pending promise if exists
        if (data.request_id && pendingRequests.has(data.request_id)) {
          const { resolve } = pendingRequests.get(data.request_id)!;
          resolve(currentMask.value);
          pendingRequests.delete(data.request_id);
        }
      } else if (data.status === 'error') {
        console.error('SAM inference error:', data.error);
        if (data.request_id && pendingRequests.has(data.request_id)) {
          const { reject } = pendingRequests.get(data.request_id)!;
          reject(new Error(data.error || 'Unknown error'));
          pendingRequests.delete(data.request_id);
        }
      }
    } catch (error) {
      console.error('Error parsing SAM WebSocket message:', error);
    }
  };

  websocket.onerror = (error) => {
    console.error('SAM WebSocket error:', error);
    wsConnected.value = false;
  };

  websocket.onclose = () => {
    console.log('SAM WebSocket closed');
    wsConnected.value = false;
    // Attempt to reconnect after delay
    setTimeout(() => {
      if (websocket?.readyState === WebSocket.CLOSED) {
        connectWebSocket();
      }
    }, 3000);
  };
}

function toggleMode(): void {
  includeMode.value = !includeMode.value;
  console.log(`Switched to ${includeMode.value ? 'include' : 'exclude'} mode`);
  // Update cursor
  if (containerRef.value && !isDragging.value) {
    containerRef.value.style.cursor = includeMode.value ? 'crosshair' : 'not-allowed';
  }
}

onMounted(() => {
  // Set up keyboard listeners
  const handleKeyPress = (e: KeyboardEvent) => {
    // Check if not typing in input
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
      return;
    }

    const key = e.key.toLowerCase();
    
    if (key === 'r') {
      resetView();
    } else if (key === 'i') {
      // Include mode
      includeMode.value = true;
      if (containerRef.value && !isDragging.value) {
        containerRef.value.style.cursor = 'crosshair';
      }
    } else if (key === 'u') {
      // Exclude/Undo mode
      includeMode.value = false;
      if (containerRef.value && !isDragging.value) {
        containerRef.value.style.cursor = 'not-allowed';
      }
    }
  };
  
  window.addEventListener('keydown', handleKeyPress);

  // Connect to WebSocket
  connectWebSocket();
  
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
  
  // Close WebSocket
  if (websocket) {
    websocket.close();
    websocket = null;
  }
  
  if (fabricCanvas) {
    try {
      fabricCanvas.dispose();
    } catch (e) {
      console.warn('Error disposing canvas on unmount:', e);
    }
    fabricCanvas = null;
    fabricImg = null;
    maskOverlay = null;
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
