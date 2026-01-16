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
import axios from 'axios';

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

// API client for saving points and masks
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1',
  timeout: 20000,
});

// Pan and zoom state
const scale = ref(1);
const position = ref({ x: 0, y: 0 });
const isDragging = ref(false);
const lastPointerPosition = ref({ x: 0, y: 0 });

// Store window event listeners for cleanup
let windowMouseMoveHandler: ((e: MouseEvent) => void) | null = null;
let windowMouseUpHandler: ((e: MouseEvent) => void) | null = null;
let resizeObserver: ResizeObserver | null = null;
let resizeTimeout: ReturnType<typeof setTimeout> | null = null;

// Image dimensions
const imageWidth = ref(0);
const imageHeight = ref(0);

// Point clicking state (CANVAS-003)
const includeMode = ref(true); // true = include (I key), false = exclude (U key)
const points = ref<Point[]>([]); // Store clicked points
const pointCircles = ref<Map<string, fabric.Circle>>(new Map()); // Store point circle objects for updates
const pointIcons = ref<Map<string, fabric.Text>>(new Map()); // Store point icon objects (plus/minus) for updates
const currentMask = ref<MaskData | null>(null); // Current SAM mask
let maskOverlay: fabric.Image | null = null; // Fabric image for mask overlay

// WebSocket connection (SAM-003)
let websocket: WebSocket | null = null;
const wsConnected = ref(false);
const pendingRequests = new Map<string, { resolve: (mask: MaskData | null) => void; reject: (error: any) => void }>();

function loadImage(url: string): void {
  const img = new Image();
  img.crossOrigin = 'anonymous';
  
  img.onload = async () => {
    imageWidth.value = img.width;
    imageHeight.value = img.height;
    imageLoaded.value = true;
    
    // Initialize canvas on next tick to ensure DOM is ready
    await nextTick();
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
      
      // Load existing points and masks after canvas is initialized
      await nextTick();
      await loadExistingData();
    }
  };
  
  img.onerror = (error) => {
    console.error('Failed to load image:', error);
  };
  
  img.src = url;
}

function initializeFabricCanvas(img: HTMLImageElement): void {
  if (!canvasRef.value || !containerRef.value) return;
  
  // Dispose old canvas if it exists
  if (fabricCanvas) {
    fabricCanvas.dispose();
    fabricImg = null;
  }
  
  // Get actual container dimensions
  const containerRect = containerRef.value.getBoundingClientRect();
  const canvasWidth = containerRect.width || props.width;
  const canvasHeight = containerRect.height || props.height;
  
  // Create fabric canvas
  fabricCanvas = new fabric.Canvas(canvasRef.value, {
    width: canvasWidth,
    height: canvasHeight,
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
  
  // Set up resize observer
  setupResizeObserver();
}

function resetView(): void {
  if (!fabricCanvas || !fabricImg) return;
  
  // Ensure no objects are selected
  fabricCanvas.discardActiveObject();
  
  // Get actual canvas dimensions
  const canvasWidth = fabricCanvas.getWidth();
  const canvasHeight = fabricCanvas.getHeight();
  
  // Calculate scale to fit image in viewport
  const scaleX = canvasWidth / imageWidth.value;
  const scaleY = canvasHeight / imageHeight.value;
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
  const centerX = (canvasWidth - scaledWidth) / 2;
  const centerY = (canvasHeight - scaledHeight) / 2;
  
  fabricImg.set({
    left: centerX,
    top: centerY,
  });
  
  // Update mask overlay position
  if (maskOverlay) {
    maskOverlay.set({
      left: centerX,
      top: centerY,
      scaleX: fitScale,
      scaleY: fitScale,
    });
  }
  
  // Update point positions
  updatePointPositions();
  
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

function setupResizeObserver(): void {
  if (!containerRef.value || !ResizeObserver) return;
  
  // Clean up existing observer
  if (resizeObserver) {
    resizeObserver.disconnect();
  }
  
  // Clear any pending resize timeout
  if (resizeTimeout) {
    clearTimeout(resizeTimeout);
    resizeTimeout = null;
  }
  
  // Create new resize observer
  resizeObserver = new ResizeObserver((entries) => {
    if (!fabricCanvas || !fabricImg) return;
    
    // Clear any pending resize
    if (resizeTimeout) {
      clearTimeout(resizeTimeout);
    }
    
    // Debounce the resize to avoid excessive updates
    resizeTimeout = setTimeout(() => {
      if (!fabricCanvas || !fabricImg) return;
      
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        
        if (width > 0 && height > 0) {
          // Use nextTick to ensure DOM has updated
          nextTick(() => {
            if (!fabricCanvas || !fabricImg) return;
            
            // Get actual container dimensions to ensure accuracy
            const containerRect = containerRef.value?.getBoundingClientRect();
            const actualWidth = containerRect?.width || width;
            const actualHeight = containerRect?.height || height;
            
            // Update canvas dimensions
            fabricCanvas.setDimensions({
              width: actualWidth,
              height: actualHeight,
            });
            
            // Recalculate image fit to new dimensions
            const scaleX = actualWidth / imageWidth.value;
            const scaleY = actualHeight / imageHeight.value;
            const fitScale = Math.min(scaleX, scaleY, 1);
            
            scale.value = fitScale;
            
            // Update image scale
            fabricImg.set({
              scaleX: fitScale,
              scaleY: fitScale,
            });
            
            // Re-center the image
            const scaledWidth = imageWidth.value * fitScale;
            const scaledHeight = imageHeight.value * fitScale;
            const centerX = (actualWidth - scaledWidth) / 2;
            const centerY = (actualHeight - scaledHeight) / 2;
            
            fabricImg.set({
              left: centerX,
              top: centerY,
            });
            
            // Update mask overlay position and scale
            if (maskOverlay) {
              maskOverlay.set({
                scaleX: fitScale,
                scaleY: fitScale,
                left: centerX,
                top: centerY,
              });
            }
            
            // Update point positions to match new canvas dimensions
            updatePointPositions();
            
            fabricCanvas.renderAll();
          });
        }
      }
    }, 50); // Small debounce delay
  });
  
  resizeObserver.observe(containerRef.value);
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
  
  // Update mask overlay position
  if (maskOverlay) {
    maskOverlay.set({
      left: currentLeft + dx,
      top: currentTop + dy,
    });
  }
  
  // Update point positions
  updatePointPositions();
  
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
  
  // Update mask overlay position and scale
  if (maskOverlay) {
    maskOverlay.set({
      left: newLeft,
      top: newTop,
      scaleX: newScale,
      scaleY: newScale,
    });
  }
  
  // Update point positions
  updatePointPositions();
  
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

  // Save points to database
  savePoints();

  // Queue SAM inference request (SAM-003: async processing)
  requestSAMInference();
}

function renderPoint(point: Point, canvasX: number, canvasY: number): void {
  if (!fabricCanvas) return;

  // Use same color for both include and exclude (label color)
  const color = props.selectedLabelColor;
  const radius = 6;
  const iconSize = 10;

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

  // Create icon (plus for include, minus for exclude)
  const iconText = point.include ? '+' : '−';
  const icon = new fabric.Text(iconText, {
    left: 0,
    top: 0,
    fontSize: iconSize,
    fill: '#ffffff',
    fontFamily: 'Arial, sans-serif',
    fontWeight: 'bold',
    textAlign: 'center',
    originX: 'center',
    originY: 'center',
    selectable: false,
    evented: false,
    charSpacing: 0,
    lineHeight: 1,
    shadow: new fabric.Shadow({
      color: 'rgba(0, 0, 0, 0.5)',
      blur: 2,
      offsetX: 0,
      offsetY: 1,
    }),
  });

  fabricCanvas.add(circle);
  fabricCanvas.add(icon);
  
  // Use setPositionByOrigin to perfectly center the icon at the desired point
  // This accounts for font metrics and ensures true visual centering
  icon.setPositionByOrigin(new fabric.Point(canvasX, canvasY), 'center', 'center');
  icon.setCoords();
  fabricCanvas?.bringToFront(circle);
  fabricCanvas?.bringToFront(icon);
  
  // Store references for updates
  pointCircles.value.set(point.id, circle);
  pointIcons.value.set(point.id, icon);
  
  fabricCanvas.renderAll();
}

function updatePointPositions(): void {
  if (!fabricCanvas || !fabricImg) return;
  
  const imgLeft = fabricImg.left || 0;
  const imgTop = fabricImg.top || 0;
  const imgScaleX = fabricImg.scaleX || 1;
  const radius = 6;
  
  // Update each point circle and icon position based on current image transform
  points.value.forEach((point) => {
    const circle = pointCircles.value.get(point.id);
    const icon = pointIcons.value.get(point.id);
    if (!circle) return;
    
    // Convert normalized coordinates to canvas coordinates
    const canvasX = imgLeft + point.x * imageWidth.value * imgScaleX;
    const canvasY = imgTop + point.y * imageHeight.value * imgScaleX;
    
    circle.set({
      left: canvasX - radius,
      top: canvasY - radius,
    });
    
    if (icon) {
      // Ensure icon stays centered on the point using setPositionByOrigin for accurate centering
      icon.setPositionByOrigin(new fabric.Point(canvasX, canvasY), 'center', 'center');
      icon.setCoords();
    }
  });
  
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

  // SAM-003: Queue request for async processing
  const requestId = `req-${Date.now()}-${Math.random()}`;

  // Create promise for this request
  const promise = new Promise<MaskData | null>((resolve, reject) => {
    pendingRequests.set(requestId, { resolve, reject });
    
    // Set timeout to reject if no response after 10 seconds
    setTimeout(() => {
      if (pendingRequests.has(requestId)) {
        pendingRequests.delete(requestId);
        reject(new Error('SAM inference timeout'));
      }
    }, 10000);
  });

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
    
    // Wait for response (async update)
    try {
      const mask = await promise;
      if (mask) {
        console.log('Received mask for request:', requestId);
      }
    } catch (error) {
      console.error('Error waiting for SAM response:', error);
    }
  } catch (error) {
    console.error('Error sending SAM request:', error);
    pendingRequests.delete(requestId);
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

  // Draw the mask first (this is the correct mask, don't modify imageData)
  ctx.putImageData(imageData, 0, 0);
  
  // Draw border/stroke around the mask for better visibility
  // Use a simpler approach: create a border by drawing on edge pixels
  const borderColor = hexToRgb(props.selectedLabelColor);
  
  // Create a copy of imageData to work with for border detection (don't modify original)
  const borderCanvas = document.createElement('canvas');
  borderCanvas.width = width;
  borderCanvas.height = height;
  const borderCtx = borderCanvas.getContext('2d');
  if (borderCtx) {
    // Draw border pixels on edges
    borderCtx.fillStyle = `rgb(${borderColor.r}, ${borderColor.g}, ${borderColor.b})`;
    
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const idx = (y * width + x) * 4;
        const alpha = imageData.data[idx + 3];
        
        // Only process mask pixels
        if (alpha > 0) {
          // Check if this is an edge pixel (has transparent neighbor)
          const neighbors = [
            [x, y - 1], [x, y + 1], [x - 1, y], [x + 1, y]
          ];
          
          let isEdge = false;
          for (const [nx, ny] of neighbors) {
            if (nx < 0 || nx >= width || ny < 0 || ny >= height) {
              isEdge = true;
              break;
            }
            const nIdx = (ny * width + nx) * 4;
            if (imageData.data[nIdx + 3] === 0) {
              isEdge = true;
              break;
            }
          }
          
          // Draw border pixel on edge
          if (isEdge) {
            borderCtx.fillRect(x, y, 1, 1);
          }
        }
      }
    }
    
    // Draw border on top of mask
    ctx.globalCompositeOperation = 'source-over';
    ctx.drawImage(borderCanvas, 0, 0);
  }

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
  
  // Bring all points to front after adding mask
  pointCircles.value.forEach((circle) => {
    fabricCanvas?.bringToFront(circle);
  });
  pointIcons.value.forEach((icon) => {
    fabricCanvas?.bringToFront(icon);
  });
  
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

async function savePoints(): Promise<void> {
  if (!props.projectId || !props.frameNumber || !props.selectedLabelId || points.value.length === 0) {
    console.warn('Cannot save points: missing required data', {
      projectId: props.projectId,
      frameNumber: props.frameNumber,
      selectedLabelId: props.selectedLabelId,
      pointsCount: points.value.length,
    });
    return;
  }

  try {
    console.log('Saving points:', {
      projectId: props.projectId,
      frameNumber: props.frameNumber,
      labelId: props.selectedLabelId,
      pointsCount: points.value.length,
    });
    
    const response = await api.post(
      `/projects/${props.projectId}/frames/${props.frameNumber}/points`,
      {
        label_id: props.selectedLabelId,
        points: points.value.map(p => ({
          x: p.x,
          y: p.y,
          include: p.include,
        })),
      }
    );
    console.log('Points saved successfully:', response.data);
  } catch (error: any) {
    console.error('Failed to save points:', error);
    if (error.response) {
      console.error('Error response:', error.response.data);
    }
  }
}

async function saveMask(maskData: MaskData): Promise<void> {
  if (!props.projectId || !props.frameNumber || !props.selectedLabelId) {
    console.warn('Cannot save mask: missing required data', {
      projectId: props.projectId,
      frameNumber: props.frameNumber,
      selectedLabelId: props.selectedLabelId,
    });
    return;
  }

  try {
    console.log('Saving mask:', {
      projectId: props.projectId,
      frameNumber: props.frameNumber,
      labelId: props.selectedLabelId,
      imageWidth: imageWidth.value,
      imageHeight: imageHeight.value,
    });
    
    // Convert RLE mask to contour polygon
    const contourPolygon = rleToContour(maskData.rle, imageWidth.value, imageHeight.value);
    const area = calculateMaskArea(maskData.rle, imageWidth.value, imageHeight.value);

    console.log('Mask conversion:', {
      contourPoints: contourPolygon.length,
      area: area,
    });

    const response = await api.post(
      `/projects/${props.projectId}/frames/${props.frameNumber}/masks`,
      {
        label_id: props.selectedLabelId,
        mask: {
          contour_polygon: contourPolygon,
          area: area,
        },
      }
    );
    console.log('Mask saved successfully:', response.data);
  } catch (error: any) {
    console.error('Failed to save mask:', error);
    if (error.response) {
      console.error('Error response:', error.response.data);
    }
  }
}

function rleToContour(rle: string, width: number, height: number): number[][] {
  // Decode RLE to binary mask
  const mask = decodeRLE(rle, width, height);
  
  // Convert binary mask to 2D array
  const mask2d: boolean[][] = [];
  for (let y = 0; y < height; y++) {
    mask2d[y] = [];
    for (let x = 0; x < width; x++) {
      const idx = y * width + x;
      mask2d[y][x] = mask[idx] > 0;
    }
  }
  
  // Find edge pixels (mask pixels with at least one non-mask neighbor)
  const edgePixels: number[][] = [];
  const directions = [[0, -1], [1, 0], [0, 1], [-1, 0]]; // Up, Right, Down, Left
  
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (mask2d[y][x]) {
        // Check if this is an edge pixel
        let isEdge = false;
        for (const [dx, dy] of directions) {
          const nx = x + dx;
          const ny = y + dy;
          if (nx < 0 || nx >= width || ny < 0 || ny >= height || !mask2d[ny][nx]) {
            isEdge = true;
            break;
          }
        }
        if (isEdge) {
          edgePixels.push([x, y]);
        }
      }
    }
  }
  
  // If no edge pixels, return empty contour
  if (edgePixels.length === 0) {
    return [];
  }
  
  // Sort edge pixels to form a reasonable contour (top to bottom, left to right)
  // Then connect them in a simple way
  edgePixels.sort((a, b) => {
    if (a[1] !== b[1]) return a[1] - b[1]; // Sort by y first
    return a[0] - b[0]; // Then by x
  });
  
  // For simplicity, return all edge pixels as the contour
  // In a production system, you'd want to use a proper contour tracing algorithm
  // like Moore neighborhood or marching squares
  return edgePixels;
}

function calculateMaskArea(rle: string, width: number, height: number): number {
  const mask = decodeRLE(rle, width, height);
  let area = 0;
  for (let i = 0; i < mask.length; i++) {
    if (mask[i] > 0) {
      area++;
    }
  }
  return area;
}

async function loadExistingData(): Promise<void> {
  if (!props.projectId || !props.frameNumber || !fabricCanvas || !fabricImg) {
    console.warn('Cannot load existing data: missing required data', {
      projectId: props.projectId,
      frameNumber: props.frameNumber,
      hasCanvas: !!fabricCanvas,
      hasImg: !!fabricImg,
    });
    return;
  }

  try {
    console.log('Loading existing data for:', {
      projectId: props.projectId,
      frameNumber: props.frameNumber,
      selectedLabelId: props.selectedLabelId,
    });
    
    // Load existing points for the current label (if selected) or all points
    const pointsParams: { label_id?: string } = {};
    if (props.selectedLabelId) {
      pointsParams.label_id = props.selectedLabelId;
    }
    
    const pointsResponse = await api.get(
      `/projects/${props.projectId}/frames/${props.frameNumber}/points`,
      { params: pointsParams }
    );
    
    console.log('Points response:', pointsResponse.data);
    
    if (pointsResponse.data && pointsResponse.data.length > 0) {
      // Clear existing points
      points.value = [];
      pointCircles.value.forEach((circle) => {
        if (fabricCanvas) {
          fabricCanvas.remove(circle);
        }
      });
      pointCircles.value.clear();
      pointIcons.value.forEach((icon) => {
        if (fabricCanvas) {
          fabricCanvas.remove(icon);
        }
      });
      pointIcons.value.clear();
      
      // Load points
      for (const pointData of pointsResponse.data) {
        const point: Point = {
          id: pointData.id,
          x: pointData.x,
          y: pointData.y,
          include: pointData.include,
        };
        points.value.push(point);
        
        // Render point
        if (fabricCanvas && fabricImg) {
          const imgLeft = fabricImg.left || 0;
          const imgTop = fabricImg.top || 0;
          const imgScaleX = fabricImg.scaleX || 1;
          const canvasX = imgLeft + point.x * imageWidth.value * imgScaleX;
          const canvasY = imgTop + point.y * imageHeight.value * imgScaleX;
          renderPoint(point, canvasX, canvasY);
        }
      }
      console.log('Loaded existing points:', points.value.length);
    } else {
      console.log('No existing points found');
    }
    
    // Load existing masks for the current label (if selected) or all masks
    const masksParams: { label_id?: string } = {};
    if (props.selectedLabelId) {
      masksParams.label_id = props.selectedLabelId;
    }
    
    const masksResponse = await api.get(
      `/projects/${props.projectId}/frames/${props.frameNumber}/masks`,
      { params: masksParams }
    );
    
    console.log('Masks response:', masksResponse.data);
    
    if (masksResponse.data && masksResponse.data.length > 0) {
      console.log('Loaded existing masks:', masksResponse.data.length);
      // Note: Rendering masks from contour polygons would require converting back to RLE
      // For now, we just log that masks exist
    } else {
      console.log('No existing masks found');
    }
  } catch (error: any) {
    console.error('Failed to load existing data:', error);
    if (error.response) {
      console.error('Error response:', error.response.data);
    }
  }
}

// Watch for image URL changes
watch(() => props.imageUrl, (newUrl) => {
  if (newUrl) {
    loadImage(newUrl);
    // Clear points when image changes
    points.value = [];
    // Remove all point circles and icons
    pointCircles.value.forEach((circle) => {
      if (fabricCanvas) {
        fabricCanvas.remove(circle);
      }
    });
    pointCircles.value.clear();
    pointIcons.value.forEach((icon) => {
      if (fabricCanvas) {
        fabricCanvas.remove(icon);
      }
    });
    pointIcons.value.clear();
    currentMask.value = null;
    if (maskOverlay && fabricCanvas) {
      fabricCanvas.remove(maskOverlay);
      maskOverlay = null;
    }
  }
}, { immediate: true });

// Watch for frame number changes to reload data
watch(() => props.frameNumber, async () => {
  if (fabricCanvas && fabricImg && props.projectId && props.frameNumber !== undefined) {
    await loadExistingData();
  }
});

// Watch for selected label changes to reload data
watch(() => props.selectedLabelId, async () => {
  if (fabricCanvas && fabricImg && props.projectId && props.frameNumber !== undefined) {
    await loadExistingData();
  }
});

// Expose reset view function and points
defineExpose({
  resetView,
  getPoints: () => points.value,
  clearPoints: () => {
    points.value = [];
    // Remove all point circles and icons
    pointCircles.value.forEach((circle) => {
      if (fabricCanvas) {
        fabricCanvas.remove(circle);
      }
    });
    pointCircles.value.clear();
    pointIcons.value.forEach((icon) => {
      if (fabricCanvas) {
        fabricCanvas.remove(icon);
      }
    });
    pointIcons.value.clear();
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

      // Handle mask responses (SAM-003: async mask updates)
      if (data.status === 'success' && data.mask_rle) {
        const maskData: MaskData = {
          rle: data.mask_rle,
          bbox: data.mask_bbox || [0, 0, 0, 0],
        };
        
        // Update current mask (async update as processed)
        currentMask.value = maskData;
        renderMask();

        // Save mask to database
        saveMask(maskData);

        // Resolve pending promise if exists
        if (data.request_id && pendingRequests.has(data.request_id)) {
          const { resolve } = pendingRequests.get(data.request_id)!;
          resolve(maskData);
          pendingRequests.delete(data.request_id);
          console.log(`Mask updated for request ${data.request_id}`);
        }
      } else if (data.status === 'error') {
        const errorMsg = data.error || 'Unknown error';
        console.error('SAM inference error:', errorMsg);

        // Clear current mask on error
        if (errorMsg.includes('not initialized') || errorMsg.includes('failed to load')) {
          // Gracefully handle SAM not being available by clearing mask overlay
          currentMask.value = null;
          if (maskOverlay && fabricCanvas) {
            fabricCanvas.remove(maskOverlay);
            maskOverlay = null;
            fabricCanvas.renderAll();
          }
          // Also mark websocket as not usable for now
          wsConnected.value = false;
        }

        // Resolve or reject pending promise if exists
        if (data.request_id && pendingRequests.has(data.request_id)) {
          const pending = pendingRequests.get(data.request_id)!;
          // If SAM isn't initialized, resolve with null to avoid throwing in UI
          if (errorMsg.includes('not initialized')) {
            pending.resolve(null);
          } else {
            pending.reject(new Error(errorMsg));
          }
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
    // Show user-friendly error message
    if (pendingRequests.size > 0) {
      const errorMsg = 'WebSocket connection error. Please refresh the page.';
      for (const [requestId, { reject }] of pendingRequests.entries()) {
        reject(new Error(errorMsg));
      }
      pendingRequests.clear();
    }
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
  
  // Clean up resize observer
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  
  // Clear any pending resize timeout
  if (resizeTimeout) {
    clearTimeout(resizeTimeout);
    resizeTimeout = null;
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
  width: 100%;
}

.image-viewer canvas {
  display: block;
  width: 100% !important;
  height: 100% !important;
  max-width: 100%;
  max-height: 100%;
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
