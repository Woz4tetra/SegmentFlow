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

    <!-- Mode indicator -->
    <div v-if="imageLoaded" class="mode-indicator" :class="{ exclude: !includeMode }">
      {{ includeMode ? '+ Include' : '− Exclude' }}
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted, watch, onBeforeUnmount, nextTick, computed } from 'vue';
import { fabric } from 'fabric';
import axios from 'axios';

interface Label {
  id: string;
  name: string;
  color_hex: string;
  thumbnail_path: string | null;
}

interface Props {
  imageUrl: string;
  width?: number;
  height?: number;
  projectId?: string;
  frameNumber?: number;
  selectedLabelId?: string;
  selectedLabelColor?: string;
  labels: Label[];
}

const props = withDefaults(defineProps<Props>(), {
  width: 1200,
  height: 800,
  projectId: '',
  frameNumber: 0,
  selectedLabelId: '',
  selectedLabelColor: '#2563eb',
  labels: () => [],
});

// Emit events to parent component
const emit = defineEmits<{
  (e: 'frame-labeled', frameNumber: number): void;
}>();

// Point stored per label
interface Point {
  x: number;
  y: number;
  include: boolean;
  id: string;
  labelId: string;
}

// Mask contour stored per label
interface MaskContour {
  labelId: string;
  contourPolygon: number[][];
  area: number;
}

const containerRef = ref<HTMLElement | null>(null);
const canvasRef = ref<HTMLCanvasElement | null>(null);
let fabricCanvas: fabric.Canvas | null = null;
let fabricImg: fabric.Image | null = null;

const imageLoaded = ref(false);

// API client
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1',
  timeout: 20000,
});

// Pan and zoom state
const scale = ref(1);
const isDragging = ref(false);
const lastPointerPosition = ref({ x: 0, y: 0 });

// Point mode (include/exclude)
const includeMode = ref(true);

// Store points and masks PER LABEL - this is the key fix
const pointsByLabel = ref<Map<string, Point[]>>(new Map());
const masksByLabel = ref<Map<string, MaskContour>>(new Map());

// Fabric objects for rendering - keyed by point ID or label ID
const pointVisuals = ref<Map<string, { circle: fabric.Circle; icon: fabric.Text }>>(new Map());
const maskVisuals = ref<Map<string, fabric.Object>>(new Map());

// Prevent concurrent loads
const isLoadingData = ref(false);

// Image dimensions
const imageWidth = ref(0);
const imageHeight = ref(0);

// WebSocket connection
let websocket: WebSocket | null = null;
const wsConnected = ref(false);

// Track the latest SAM request ID per label to ignore out-of-order responses
const latestRequestByLabel = ref<Map<string, string>>(new Map());

// Cleanup references
let resizeObserver: ResizeObserver | null = null;
let resizeTimeout: ReturnType<typeof setTimeout> | null = null;

// Store event handler references for cleanup
let containerMouseDownHandler: ((e: MouseEvent) => void) | null = null;
let containerContextMenuHandler: ((e: Event) => void) | null = null;
let containerWheelHandler: ((e: WheelEvent) => void) | null = null;

// Get color for a label by ID
function getLabelColor(labelId: string): string {
  const label = props.labels.find(l => l.id === labelId);
  return label?.color_hex || '#2563eb';
}

// Load the image
function loadImage(url: string): void {
  const img = new Image();
  img.crossOrigin = 'anonymous';
  
  img.onload = async () => {
    imageWidth.value = img.width;
    imageHeight.value = img.height;
    imageLoaded.value = true;
    
    await nextTick();
    if (canvasRef.value) {
      initializeFabricCanvas(img);
      await nextTick();
      await loadAllExistingData();
    }
  };
  
  img.onerror = (error) => {
    console.error('Failed to load image:', error);
  };
  
  img.src = url;
}

function initializeFabricCanvas(img: HTMLImageElement): void {
  if (!canvasRef.value || !containerRef.value) return;
  
  // Dispose old canvas
  if (fabricCanvas) {
    fabricCanvas.dispose();
    fabricImg = null;
    pointVisuals.value.clear();
    maskVisuals.value.clear();
  }
  
  const containerRect = containerRef.value.getBoundingClientRect();
  const canvasWidth = containerRect.width || props.width;
  const canvasHeight = containerRect.height || props.height;
  
  fabricCanvas = new fabric.Canvas(canvasRef.value, {
    width: canvasWidth,
    height: canvasHeight,
    backgroundColor: '#1a1a1a',
    selection: false,
    preserveObjectStacking: true,
  });
  
  fabricImg = new fabric.Image(img, {
    left: 0,
    top: 0,
    selectable: false,
    evented: false,
    hoverCursor: 'default',
    moveCursor: 'default',
  });
  
  fabricCanvas.add(fabricImg);
  fabricCanvas.renderAll();
  
  resetView();
  setupEventHandlers();
  setupResizeObserver();
}

function resetView(): void {
  if (!fabricCanvas || !fabricImg) return;
  
  fabricCanvas.discardActiveObject();
  
  const canvasWidth = fabricCanvas.getWidth();
  const canvasHeight = fabricCanvas.getHeight();
  
  const scaleX = canvasWidth / imageWidth.value;
  const scaleY = canvasHeight / imageHeight.value;
  const fitScale = Math.min(scaleX, scaleY, 1);
  
  scale.value = fitScale;
  
  fabricImg.set({
    scaleX: fitScale,
    scaleY: fitScale,
  });
  
  const scaledWidth = imageWidth.value * fitScale;
  const scaledHeight = imageHeight.value * fitScale;
  const centerX = (canvasWidth - scaledWidth) / 2;
  const centerY = (canvasHeight - scaledHeight) / 2;
  
  fabricImg.set({
    left: centerX,
    top: centerY,
  });
  
  updateAllVisualPositions();
  fabricCanvas.renderAll();
}

function cleanupEventHandlers(): void {
  const container = containerRef.value;
  if (!container) return;
  
  // Remove old handlers if they exist
  if (containerMouseDownHandler) {
    container.removeEventListener('mousedown', containerMouseDownHandler);
    containerMouseDownHandler = null;
  }
  if (containerContextMenuHandler) {
    container.removeEventListener('contextmenu', containerContextMenuHandler);
    containerContextMenuHandler = null;
  }
  if (containerWheelHandler) {
    container.removeEventListener('wheel', containerWheelHandler);
    containerWheelHandler = null;
  }
}

function setupEventHandlers(): void {
  if (!fabricCanvas || !containerRef.value) return;
  
  const container = containerRef.value;
  
  // Clean up any existing handlers first to prevent duplicates
  cleanupEventHandlers();
  
  // Disable Fabric.js selection
  fabricCanvas.on('selection:created', () => {
    fabricCanvas?.discardActiveObject();
  });
  fabricCanvas.on('selection:updated', () => {
    fabricCanvas?.discardActiveObject();
  });
  
  // Create and store mousedown handler
  containerMouseDownHandler = (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (e.button === 2) {
      // Right click - start panning
      startPan(e);
    } else if (e.button === 0) {
      // Left click - add point
      handleClick(e);
    }
  };
  
  // Create and store contextmenu handler
  containerContextMenuHandler = (e: Event) => {
    e.preventDefault();
    e.stopPropagation();
  };
  
  // Store wheel handler reference
  containerWheelHandler = handleWheel;
  
  // Add event listeners
  container.addEventListener('mousedown', containerMouseDownHandler);
  container.addEventListener('contextmenu', containerContextMenuHandler);
  container.addEventListener('wheel', containerWheelHandler, { passive: false });
}

function startPan(e: MouseEvent): void {
  isDragging.value = true;
  lastPointerPosition.value = { x: e.clientX, y: e.clientY };
  
  if (containerRef.value) {
    containerRef.value.style.cursor = 'grabbing';
  }
  
  const handleMouseMove = (e: MouseEvent) => {
    if (!isDragging.value || !fabricCanvas || !fabricImg) return;
    
    e.preventDefault();
    
    const dx = e.clientX - lastPointerPosition.value.x;
    const dy = e.clientY - lastPointerPosition.value.y;
    
    if (Math.abs(dx) < 0.1 && Math.abs(dy) < 0.1) return;
    
    const currentLeft = fabricImg.left || 0;
    const currentTop = fabricImg.top || 0;
    
    fabricImg.set({
      left: currentLeft + dx,
      top: currentTop + dy,
    });
    
    updateAllVisualPositions();
    fabricCanvas.renderAll();
    
    lastPointerPosition.value = { x: e.clientX, y: e.clientY };
  };
  
  const handleMouseUp = () => {
    isDragging.value = false;
    if (containerRef.value) {
      containerRef.value.style.cursor = 'crosshair';
    }
    window.removeEventListener('mousemove', handleMouseMove);
    window.removeEventListener('mouseup', handleMouseUp);
  };
  
  window.addEventListener('mousemove', handleMouseMove);
  window.addEventListener('mouseup', handleMouseUp);
}

function handleWheel(e: WheelEvent): void {
  if (!fabricCanvas || !fabricImg || !containerRef.value) return;
  
  e.preventDefault();
  
  const oldScale = scale.value;
  const rect = containerRef.value.getBoundingClientRect();
  const pointer = {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
  };
  
  const scaleBy = 1.05;
  const direction = e.deltaY > 0 ? -1 : 1;
  
  let newScale = direction > 0 ? oldScale * scaleBy : oldScale / scaleBy;
  newScale = Math.max(0.1, Math.min(newScale, 10));
  
  const imgLeft = fabricImg.left || 0;
  const imgTop = fabricImg.top || 0;
  const imgScaleX = fabricImg.scaleX || 1;
  
  const imgX = (pointer.x - imgLeft) / imgScaleX;
  const imgY = (pointer.y - imgTop) / imgScaleX;
  
  fabricImg.set({
    scaleX: newScale,
    scaleY: newScale,
  });
  
  const newLeft = pointer.x - imgX * newScale;
  const newTop = pointer.y - imgY * newScale;
  
  fabricImg.set({
    left: newLeft,
    top: newTop,
  });
  
  updateAllVisualPositions();
  fabricCanvas.renderAll();
  
  scale.value = newScale;
}

function handleClick(e: MouseEvent): void {
  if (!fabricCanvas || !fabricImg || !props.projectId || !props.selectedLabelId) {
    console.warn('Cannot add point: missing required data', {
      hasCanvas: !!fabricCanvas,
      hasImg: !!fabricImg,
      projectId: props.projectId,
      selectedLabelId: props.selectedLabelId,
    });
    return;
  }
  
  // Don't allow clicks while data is loading - prevents race conditions with orphaned visuals
  if (isLoadingData.value) {
    console.log('Click ignored - data load in progress');
    return;
  }
  
  if (!containerRef.value) return;
  
  const rect = containerRef.value.getBoundingClientRect();
  const canvasX = e.clientX - rect.left;
  const canvasY = e.clientY - rect.top;
  
  const imgLeft = fabricImg.left || 0;
  const imgTop = fabricImg.top || 0;
  const imgScaleX = fabricImg.scaleX || 1;
  
  const imgX = (canvasX - imgLeft) / imgScaleX;
  const imgY = (canvasY - imgTop) / imgScaleX;
  
  // Normalize coordinates
  const normalizedX = imgX / imageWidth.value;
  const normalizedY = imgY / imageHeight.value;
  
  // Check bounds
  if (normalizedX < 0 || normalizedX > 1 || normalizedY < 0 || normalizedY > 1) {
    console.warn('Click outside image bounds');
    return;
  }
  
  // Create point for the CURRENT label
  const point: Point = {
    x: normalizedX,
    y: normalizedY,
    include: includeMode.value,
    id: `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
    labelId: props.selectedLabelId,
  };
  
  // Add to the label's point list
  if (!pointsByLabel.value.has(props.selectedLabelId)) {
    pointsByLabel.value.set(props.selectedLabelId, []);
  }
  pointsByLabel.value.get(props.selectedLabelId)!.push(point);
  
  console.log('Added point:', point, 'Total points for label:', pointsByLabel.value.get(props.selectedLabelId)?.length);
  
  // Render the point visually
  renderPoint(point);
  
  // Save points for this label to backend
  savePointsForLabel(props.selectedLabelId);
  
  // Request SAM inference via WebSocket for quick preview
  requestSAMInference(props.selectedLabelId);
}

function renderPoint(point: Point): void {
  if (!fabricCanvas) return;
  
  // Don't render if we're in the middle of loading data (except when called from loadAllExistingData itself)
  // This check is skipped during load because loadAllExistingData calls renderPoint after clearing
  
  // Remove existing visual for this point if it exists
  const existingVisual = pointVisuals.value.get(point.id);
  if (existingVisual) {
    fabricCanvas.remove(existingVisual.circle);
    fabricCanvas.remove(existingVisual.icon);
    pointVisuals.value.delete(point.id);
  }
  
  const color = getLabelColor(point.labelId);
  const radius = 6;
  const iconSize = 10;
  
  // Calculate canvas position
  const canvasPos = normalizedToCanvas(point.x, point.y);
  
  // Create circle
  const circle = new fabric.Circle({
    left: canvasPos.x - radius,
    top: canvasPos.y - radius,
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
  
  // Create icon (+/-)
  const iconText = point.include ? '+' : '−';
  const icon = new fabric.Text(iconText, {
    fontSize: iconSize,
    fill: '#ffffff',
    fontFamily: 'Arial, sans-serif',
    fontWeight: 'bold',
    textAlign: 'center',
    originX: 'center',
    originY: 'center',
    selectable: false,
    evented: false,
    shadow: new fabric.Shadow({
      color: 'rgba(0, 0, 0, 0.5)',
      blur: 2,
      offsetX: 0,
      offsetY: 1,
    }),
  });
  
  fabricCanvas.add(circle);
  fabricCanvas.add(icon);
  
  icon.setPositionByOrigin(new fabric.Point(canvasPos.x, canvasPos.y), 'center', 'center');
  icon.setCoords();
  
  fabricCanvas.bringToFront(circle);
  fabricCanvas.bringToFront(icon);
  
  // Store visual references
  pointVisuals.value.set(point.id, { circle, icon });
  
  fabricCanvas.renderAll();
}

function normalizedToCanvas(normX: number, normY: number): { x: number; y: number } {
  if (!fabricImg) return { x: 0, y: 0 };
  
  const imgLeft = fabricImg.left || 0;
  const imgTop = fabricImg.top || 0;
  const imgScaleX = fabricImg.scaleX || 1;
  
  return {
    x: imgLeft + normX * imageWidth.value * imgScaleX,
    y: imgTop + normY * imageHeight.value * imgScaleX,
  };
}

function updateAllVisualPositions(): void {
  if (!fabricCanvas || !fabricImg) return;
  
  const radius = 6;
  
  // Update all point positions
  for (const [labelId, points] of pointsByLabel.value) {
    for (const point of points) {
      const visual = pointVisuals.value.get(point.id);
      if (!visual) continue;
      
      const canvasPos = normalizedToCanvas(point.x, point.y);
      
      visual.circle.set({
        left: canvasPos.x - radius,
        top: canvasPos.y - radius,
      });
      
      visual.icon.setPositionByOrigin(
        new fabric.Point(canvasPos.x, canvasPos.y),
        'center',
        'center'
      );
      visual.icon.setCoords();
    }
  }
  
  // Update all mask positions to match the image transform
  for (const [labelId, maskObj] of maskVisuals.value) {
    // Masks are fabric.Image objects that should match the main image's position/scale
    maskObj.set({
      left: fabricImg.left,
      top: fabricImg.top,
      scaleX: fabricImg.scaleX,
      scaleY: fabricImg.scaleY,
    });
    maskObj.setCoords();
  }
  
  fabricCanvas.renderAll();
}

async function savePointsForLabel(labelId: string): Promise<void> {
  const points = pointsByLabel.value.get(labelId);
  if (!points || points.length === 0 || !props.projectId || props.frameNumber === undefined) {
    return;
  }
  
  try {
    console.log('Saving points for label:', labelId, 'Count:', points.length);
    
    await api.post(
      `/projects/${props.projectId}/frames/${props.frameNumber}/points`,
      {
        label_id: labelId,
        points: points.map(p => ({
          x: p.x,
          y: p.y,
          include: p.include,
        })),
      }
    );
    
    console.log('Points saved successfully for label:', labelId);
    
    // Notify parent that this frame has been labeled
    emit('frame-labeled', props.frameNumber);
  } catch (error: any) {
    console.error('Failed to save points:', error);
    if (error.response) {
      console.error('Error response:', error.response.data);
    }
  }
}

function requestSAMInference(labelId: string): void {
  const points = pointsByLabel.value.get(labelId);
  if (!points || points.length === 0) return;
  
  if (!websocket || websocket.readyState !== WebSocket.OPEN) {
    console.warn('WebSocket not connected, cannot request SAM inference');
    return;
  }
  
  const requestId = `req-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
  
  // Track this as the latest request for this label
  // Any older responses that arrive later will be ignored
  latestRequestByLabel.value.set(labelId, requestId);
  
  const request = {
    project_id: props.projectId,
    frame_number: props.frameNumber,
    label_id: labelId,
    points: points.map(p => [p.x, p.y]),
    labels: points.map(p => (p.include ? 1 : 0)),
    request_id: requestId,
  };
  
  console.log('Sending SAM request:', request);
  websocket.send(JSON.stringify(request));
}

function renderMaskContour(mask: MaskContour): void {
  if (!fabricCanvas || !fabricImg || !mask.contourPolygon || mask.contourPolygon.length === 0) {
    return;
  }
  
  // Remove ALL existing mask visuals for this label - scan canvas objects directly
  // This is more reliable than relying on the Map which might have stale references
  const objectsToRemove: fabric.Object[] = [];
  fabricCanvas.getObjects().forEach((obj: any) => {
    if (obj.isMaskOverlay && obj.maskLabelId === mask.labelId) {
      objectsToRemove.push(obj);
    }
  });
  
  for (const obj of objectsToRemove) {
    fabricCanvas.remove(obj);
  }
  
  // Also clear from our tracking maps
  maskVisuals.value.delete(mask.labelId);
  
  // Force a render to ensure the old mask is visually cleared before drawing new one
  fabricCanvas.renderAll();
  
  const width = imageWidth.value;
  const height = imageHeight.value;
  
  if (width === 0 || height === 0) return;
  if (mask.contourPolygon.length < 3) return;
  
  // Create a canvas to render the mask as a filled polygon bitmap
  const tempCanvas = document.createElement('canvas');
  tempCanvas.width = width;
  tempCanvas.height = height;
  const ctx = tempCanvas.getContext('2d');
  if (!ctx) return;
  
  // Parse the label color
  const color = getLabelColor(mask.labelId);
  const rgb = hexToRgb(color);
  
  // Draw the filled polygon
  ctx.fillStyle = `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.4)`;
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  
  ctx.beginPath();
  const firstPoint = mask.contourPolygon[0];
  ctx.moveTo(firstPoint[0], firstPoint[1]);
  
  for (let i = 1; i < mask.contourPolygon.length; i++) {
    const point = mask.contourPolygon[i];
    ctx.lineTo(point[0], point[1]);
  }
  
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  
  // Create fabric image from the mask canvas (contour version)
  // Add custom properties to identify this as a mask overlay for easy removal later
  const maskImage = new fabric.Image(tempCanvas, {
    left: fabricImg.left,
    top: fabricImg.top,
    scaleX: fabricImg.scaleX,
    scaleY: fabricImg.scaleY,
    selectable: false,
    evented: false,
  }) as fabric.Image & { isMaskOverlay: boolean; maskLabelId: string };
  
  // Mark this object as a mask overlay so we can find and remove it later
  maskImage.isMaskOverlay = true;
  maskImage.maskLabelId = mask.labelId;
  
  fabricCanvas.add(maskImage);
  fabricCanvas.moveTo(maskImage, 1); // Behind points but in front of image
  
  // Bring all points to front
  for (const visual of pointVisuals.value.values()) {
    fabricCanvas.bringToFront(visual.circle);
    fabricCanvas.bringToFront(visual.icon);
  }
  
  maskVisuals.value.set(mask.labelId, maskImage);
  fabricCanvas.renderAll();
  
  console.log('Rendered mask contour for label:', mask.labelId);
}

async function loadAllExistingData(): Promise<void> {
  if (!props.projectId || props.frameNumber === undefined || !fabricCanvas || !fabricImg) {
    return;
  }
  
  // Prevent concurrent loads
  if (isLoadingData.value) {
    console.log('Load already in progress, skipping...');
    return;
  }
  
  isLoadingData.value = true;
  
  try {
    console.log('Loading all existing data for frame:', props.frameNumber);
    
    // Clear existing data - this removes all visuals from canvas
    clearAllVisuals();
    pointsByLabel.value.clear();
    masksByLabel.value.clear();
    
    // Ensure canvas is clean before loading
    await nextTick();
    
    // Load points for ALL labels (don't filter by label_id)
    const pointsResponse = await api.get(
      `/projects/${props.projectId}/frames/${props.frameNumber}/points`
    );
    
    if (pointsResponse.data && pointsResponse.data.length > 0) {
      console.log('Loaded points:', pointsResponse.data.length);
      
      // Group points by label
      for (const pointData of pointsResponse.data) {
        const labelId = pointData.label_id || props.selectedLabelId;
        
        if (!pointsByLabel.value.has(labelId)) {
          pointsByLabel.value.set(labelId, []);
        }
        
        const point: Point = {
          id: pointData.id,
          x: pointData.x,
          y: pointData.y,
          include: pointData.include,
          labelId: labelId,
        };
        
        pointsByLabel.value.get(labelId)!.push(point);
        renderPoint(point);
      }
    }
    
    // Load masks for ALL labels (don't filter by label_id)
    const masksResponse = await api.get(
      `/projects/${props.projectId}/frames/${props.frameNumber}/masks`
    );
    
    if (masksResponse.data && masksResponse.data.length > 0) {
      console.log('Loaded masks:', masksResponse.data.length);
      
      for (const maskData of masksResponse.data) {
        const labelId = maskData.label_id || props.selectedLabelId;
        
        const mask: MaskContour = {
          labelId: labelId,
          contourPolygon: maskData.contour_polygon,
          area: maskData.area,
        };
        
        masksByLabel.value.set(labelId, mask);
        renderMaskContour(mask);
      }
    }
  } catch (error: any) {
    console.error('Failed to load existing data:', error);
    if (error.response) {
      console.error('Error response:', error.response.data);
    }
  } finally {
    isLoadingData.value = false;
  }
}

function clearAllVisuals(): void {
  if (!fabricCanvas) return;
  
  // Remove all point visuals - create array copy to avoid iteration issues
  const pointVisualsToRemove = Array.from(pointVisuals.value.values());
  for (const visual of pointVisualsToRemove) {
    try {
      fabricCanvas.remove(visual.circle);
      fabricCanvas.remove(visual.icon);
    } catch (e) {
      // Ignore errors if object already removed
      console.debug('Error removing point visual:', e);
    }
  }
  pointVisuals.value.clear();
  
  // Remove all mask visuals - first from the map
  const maskVisualsToRemove = Array.from(maskVisuals.value.values());
  for (const maskObj of maskVisualsToRemove) {
    try {
      fabricCanvas.remove(maskObj);
    } catch (e) {
      // Ignore errors if object already removed
      console.debug('Error removing mask visual:', e);
    }
  }
  maskVisuals.value.clear();
  
  // Also scan canvas directly for any mask overlays that might have been missed
  // This catches orphaned masks that weren't properly tracked in the map
  const allMaskOverlays: fabric.Object[] = [];
  fabricCanvas.getObjects().forEach((obj: any) => {
    if (obj.isMaskOverlay) {
      allMaskOverlays.push(obj);
    }
  });
  for (const obj of allMaskOverlays) {
    try {
      fabricCanvas.remove(obj);
    } catch (e) {
      console.debug('Error removing orphaned mask overlay:', e);
    }
  }
  
  fabricCanvas.renderAll();
}

function setupResizeObserver(): void {
  if (!containerRef.value || !ResizeObserver) return;
  
  if (resizeObserver) {
    resizeObserver.disconnect();
  }
  
  if (resizeTimeout) {
    clearTimeout(resizeTimeout);
    resizeTimeout = null;
  }
  
  resizeObserver = new ResizeObserver((entries) => {
    if (!fabricCanvas || !fabricImg) return;
    
    if (resizeTimeout) {
      clearTimeout(resizeTimeout);
    }
    
    resizeTimeout = setTimeout(() => {
      if (!fabricCanvas || !fabricImg || !containerRef.value) return;
      
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        
        if (width > 0 && height > 0) {
          nextTick(() => {
            if (!fabricCanvas || !fabricImg) return;
            
            const containerRect = containerRef.value?.getBoundingClientRect();
            const actualWidth = containerRect?.width || width;
            const actualHeight = containerRect?.height || height;
            
            fabricCanvas.setDimensions({
              width: actualWidth,
              height: actualHeight,
            });
            
            const scaleX = actualWidth / imageWidth.value;
            const scaleY = actualHeight / imageHeight.value;
            const fitScale = Math.min(scaleX, scaleY, 1);
            
            scale.value = fitScale;
            
            fabricImg.set({
              scaleX: fitScale,
              scaleY: fitScale,
            });
            
            const scaledWidth = imageWidth.value * fitScale;
            const scaledHeight = imageHeight.value * fitScale;
            const centerX = (actualWidth - scaledWidth) / 2;
            const centerY = (actualHeight - scaledHeight) / 2;
            
            fabricImg.set({
              left: centerX,
              top: centerY,
            });
            
            updateAllVisualPositions();
            fabricCanvas.renderAll();
          });
        }
      }
    }, 50);
  });
  
  resizeObserver.observe(containerRef.value);
}

function connectWebSocket(): void {
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    return;
  }
  
  const wsUrl = `ws://localhost:8000/api/v1/sam3/inference`;
  console.log('Connecting to SAM WebSocket:', wsUrl);
  
  websocket = new WebSocket(wsUrl);
  
  websocket.onopen = () => {
    console.log('SAM WebSocket connected');
    wsConnected.value = true;
  };
  
  websocket.onmessage = async (event) => {
    try {
      const data = JSON.parse(event.data);
      console.log('Received SAM response:', data);
      
      // Handle queue status
      if (data.queue_size !== undefined) {
        return;
      }
      
      // Handle mask response
      // Note: The mask is already being saved by the backend when points are saved
      // (see save_labeled_points endpoint which runs SAM inference in background)
      // So we don't need to save it again here - just render it for preview
      if (data.status === 'success' && data.mask_rle) {
        const labelId = data.label_id;
        const requestId = data.request_id;
        
        // Check if this response is for the latest request for this label
        // If not, ignore it to prevent out-of-order responses from showing stale masks
        const latestRequest = latestRequestByLabel.value.get(labelId);
        if (latestRequest && requestId !== latestRequest) {
          console.log('Ignoring stale SAM response:', requestId, 'latest is:', latestRequest);
          return;
        }
        
        // Render the mask from RLE for immediate preview
        // The backend has already saved it when points were saved
        // Note: We do NOT auto-reload from database here because it causes race conditions
        // when user adds multiple points quickly. The RLE preview is accurate and the
        // contour-based mask will be loaded when navigating to another frame and back,
        // or on page refresh.
        renderMaskFromRLE(data.mask_rle, labelId);
      } else if (data.status === 'error') {
        console.error('SAM inference error:', data.error);
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
    // Attempt reconnect
    setTimeout(() => {
      if (!websocket || websocket.readyState === WebSocket.CLOSED) {
        connectWebSocket();
      }
    }, 3000);
  };
}

function renderMaskFromRLE(rle: string, labelId: string): void {
  if (!fabricCanvas || !fabricImg || !rle || rle.length === 0) return;
  
  // Don't render if we're in the middle of loading data - prevents orphaned visuals
  if (isLoadingData.value) {
    console.log('Skipping RLE render - data load in progress');
    return;
  }
  
  const width = imageWidth.value;
  const height = imageHeight.value;
  
  // Decode RLE to binary mask
  const mask = new Uint8Array(width * height);
  const pairs = rle.split(';');
  
  for (const pair of pairs) {
    const [startStr, lengthStr] = pair.split(',');
    const start = parseInt(startStr, 10);
    const length = parseInt(lengthStr, 10);
    
    if (isNaN(start) || isNaN(length)) continue;
    
    for (let i = 0; i < length && start + i < mask.length; i++) {
      mask[start + i] = 1;
    }
  }
  
  // Remove ALL existing mask visuals for this label - scan canvas objects directly
  // This is more reliable than relying on the Map which might have stale references
  const objectsToRemove: fabric.Object[] = [];
  fabricCanvas.getObjects().forEach((obj: any) => {
    if (obj.isMaskOverlay && obj.maskLabelId === labelId) {
      objectsToRemove.push(obj);
    }
  });
  
  for (const obj of objectsToRemove) {
    fabricCanvas.remove(obj);
  }
  
  // Also clear from our tracking maps
  maskVisuals.value.delete(labelId);
  masksByLabel.value.delete(labelId);
  
  // Force a render to ensure the old mask is visually cleared before drawing new one
  fabricCanvas.renderAll();
  
  // Create a canvas to render the mask as an image
  const tempCanvas = document.createElement('canvas');
  tempCanvas.width = width;
  tempCanvas.height = height;
  const ctx = tempCanvas.getContext('2d');
  if (!ctx) return;
  
  // Parse the label color
  const color = getLabelColor(labelId);
  const rgb = hexToRgb(color);
  
  // Create image data with the mask (filled area)
  const imageData = ctx.createImageData(width, height);
  for (let i = 0; i < mask.length; i++) {
    if (mask[i] === 1) {
      const pixelIdx = i * 4;
      imageData.data[pixelIdx] = rgb.r;
      imageData.data[pixelIdx + 1] = rgb.g;
      imageData.data[pixelIdx + 2] = rgb.b;
      imageData.data[pixelIdx + 3] = 128; // 50% opacity
    }
  }
  ctx.putImageData(imageData, 0, 0);
  
  // Draw border by finding edge pixels and drawing them with full opacity
  const mask2d: boolean[][] = [];
  for (let y = 0; y < height; y++) {
    mask2d[y] = [];
    for (let x = 0; x < width; x++) {
      const idx = y * width + x;
      mask2d[y][x] = mask[idx] > 0;
    }
  }
  
  const directions = [[0, -1], [1, 0], [0, 1], [-1, 0], [-1, -1], [1, -1], [-1, 1], [1, 1]];
  const borderImageData = ctx.getImageData(0, 0, width, height);
  
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
          const pixelIdx = (y * width + x) * 4;
          borderImageData.data[pixelIdx] = rgb.r;
          borderImageData.data[pixelIdx + 1] = rgb.g;
          borderImageData.data[pixelIdx + 2] = rgb.b;
          borderImageData.data[pixelIdx + 3] = 255; // Full opacity for border
        }
      }
    }
  }
  ctx.putImageData(borderImageData, 0, 0);
  
  // Create fabric image from the mask canvas (RLE version)
  // Add custom properties to identify this as a mask overlay for easy removal later
  const maskImage = new fabric.Image(tempCanvas, {
    left: fabricImg.left,
    top: fabricImg.top,
    scaleX: fabricImg.scaleX,
    scaleY: fabricImg.scaleY,
    selectable: false,
    evented: false,
  }) as fabric.Image & { isMaskOverlay: boolean; maskLabelId: string };
  
  // Mark this object as a mask overlay so we can find and remove it later
  maskImage.isMaskOverlay = true;
  maskImage.maskLabelId = labelId;
  
  fabricCanvas.add(maskImage);
  fabricCanvas.moveTo(maskImage, 1); // Behind points but in front of image
  
  // Bring all points to front
  for (const visual of pointVisuals.value.values()) {
    fabricCanvas.bringToFront(visual.circle);
    fabricCanvas.bringToFront(visual.icon);
  }
  
  maskVisuals.value.set(labelId, maskImage);
  fabricCanvas.renderAll();
  
  console.log('Rendered mask from RLE for label:', labelId);
}

function rleToContour(rle: string, width: number, height: number): number[][] {
  // Decode RLE to binary mask
  const mask = new Uint8Array(width * height);
  const pairs = rle.split(';');
  
  for (const pair of pairs) {
    const [startStr, lengthStr] = pair.split(',');
    const start = parseInt(startStr, 10);
    const length = parseInt(lengthStr, 10);
    
    if (isNaN(start) || isNaN(length)) continue;
    
    for (let i = 0; i < length && start + i < mask.length; i++) {
      mask[start + i] = 1;
    }
  }
  
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
  
  // Sort edge pixels to form a reasonable contour
  edgePixels.sort((a, b) => {
    if (a[1] !== b[1]) return a[1] - b[1]; // Sort by y first
    return a[0] - b[0]; // Then by x
  });
  
  return edgePixels;
}

function calculateMaskArea(rle: string, width: number, height: number): number {
  const mask = new Uint8Array(width * height);
  const pairs = rle.split(';');
  
  for (const pair of pairs) {
    const [startStr, lengthStr] = pair.split(',');
    const start = parseInt(startStr, 10);
    const length = parseInt(lengthStr, 10);
    
    if (isNaN(start) || isNaN(length)) continue;
    
    for (let i = 0; i < length && start + i < mask.length; i++) {
      mask[start + i] = 1;
    }
  }
  
  let area = 0;
  for (let i = 0; i < mask.length; i++) {
    if (mask[i] > 0) {
      area++;
    }
  }
  return area;
}

async function saveMaskFromRLE(rle: string, labelId: string): Promise<void> {
  if (!props.projectId || props.frameNumber === undefined || props.frameNumber === null || !labelId) {
    console.warn('Cannot save mask: missing required data', {
      projectId: props.projectId,
      frameNumber: props.frameNumber,
      labelId: labelId,
    });
    return;
  }

  try {
    console.log('Saving mask from RLE for label:', labelId);
    
    // Convert RLE mask to contour polygon
    const contourPolygon = rleToContour(rle, imageWidth.value, imageHeight.value);
    const area = calculateMaskArea(rle, imageWidth.value, imageHeight.value);

    console.log('Mask conversion:', {
      contourPoints: contourPolygon.length,
      area: area,
    });

    // Validate contour polygon
    if (!contourPolygon || contourPolygon.length === 0) {
      console.warn('Cannot save mask: empty contour polygon');
      return;
    }

    // Ensure all contour points are valid [x, y] pairs and convert to floats
    const validContour = contourPolygon
      .filter(point => 
        Array.isArray(point) && point.length === 2 && 
        typeof point[0] === 'number' && typeof point[1] === 'number'
      )
      .map(point => [Number.parseFloat(point[0].toString()), Number.parseFloat(point[1].toString())]);

    if (validContour.length === 0) {
      console.warn('Cannot save mask: no valid contour points');
      return;
    }

    // Ensure area is a valid float
    const validArea = Number.parseFloat(area.toString());
    if (isNaN(validArea) || validArea < 0) {
      console.warn('Cannot save mask: invalid area', validArea);
      return;
    }

    const requestBody = {
      label_id: labelId,
      mask: {
        contour_polygon: validContour,
        area: validArea,
      },
    };

        const response = await api.post(
          `/projects/${props.projectId}/frames/${props.frameNumber}/masks`,
          requestBody
        );
        console.log('Mask saved successfully:', response.data);
        
        // Don't update masksByLabel here - let loadAllExistingData handle it
        // This prevents double rendering (RLE render + contour render)
  } catch (error: any) {
    console.error('Failed to save mask:', error);
    if (error.response) {
      console.error('Error response:', error.response.data);
    }
  }
}

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  hex = hex.replace('#', '');
  return {
    r: parseInt(hex.substring(0, 2), 16),
    g: parseInt(hex.substring(2, 4), 16),
    b: parseInt(hex.substring(4, 6), 16),
  };
}

// Watch for image URL changes - load new image
watch(() => props.imageUrl, (newUrl) => {
  if (newUrl) {
    clearAllVisuals();
    pointsByLabel.value.clear();
    masksByLabel.value.clear();
    latestRequestByLabel.value.clear(); // Clear pending request tracking
    loadImage(newUrl);
  }
}, { immediate: true });

// Watch for frame changes - reload data
watch(() => props.frameNumber, async () => {
  if (fabricCanvas && fabricImg && props.projectId) {
    // Clear visuals before loading new data to prevent duplicates
    clearAllVisuals();
    pointsByLabel.value.clear();
    masksByLabel.value.clear();
    latestRequestByLabel.value.clear(); // Clear pending request tracking
    await loadAllExistingData();
  }
});

// Note: We do NOT reload when selectedLabelId changes
// because we now show ALL labels' points at once
// The selectedLabelId only affects which label new clicks are assigned to

// Keyboard handlers
function handleKeyPress(e: KeyboardEvent): void {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
    return;
  }
  
  const key = e.key.toLowerCase();
  
  if (key === 'r') {
    resetView();
  } else if (key === 'i') {
    includeMode.value = true;
    if (containerRef.value) {
      containerRef.value.style.cursor = 'crosshair';
    }
  } else if (key === 'u') {
    includeMode.value = false;
    if (containerRef.value) {
      containerRef.value.style.cursor = 'not-allowed';
    }
  }
}

// Expose methods
defineExpose({
  resetView,
  getPointsByLabel: () => pointsByLabel.value,
  clearAllPoints: () => {
    clearAllVisuals();
    pointsByLabel.value.clear();
    masksByLabel.value.clear();
  },
});

onMounted(() => {
  window.addEventListener('keydown', handleKeyPress);
  connectWebSocket();
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeyPress);
  
  // Clean up container event handlers
  cleanupEventHandlers();
  
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  
  if (resizeTimeout) {
    clearTimeout(resizeTimeout);
    resizeTimeout = null;
  }
  
  if (websocket) {
    websocket.close();
    websocket = null;
  }
  
  if (fabricCanvas) {
    try {
      fabricCanvas.dispose();
    } catch (e) {
      console.warn('Error disposing canvas:', e);
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
  width: 100%;
  cursor: crosshair;
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

.mode-indicator {
  position: absolute;
  top: 12px;
  right: 12px;
  padding: 6px 12px;
  background: rgba(34, 197, 94, 0.9);
  color: white;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 6px;
  pointer-events: none;
  transition: background 0.2s ease;
}

.mode-indicator.exclude {
  background: rgba(239, 68, 68, 0.9);
}
</style>

