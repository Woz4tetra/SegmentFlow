<template>
  <div class="crop-selector">
    <div class="crop-stage" ref="stageRef">
      <img class="crop-image" :src="src" alt="Source frame" draggable="false" />

      <!-- Dimmed region outside the crop -->
      <div class="crop-shade" :style="shadeStyle.top"></div>
      <div class="crop-shade" :style="shadeStyle.bottom"></div>
      <div class="crop-shade" :style="shadeStyle.left"></div>
      <div class="crop-shade" :style="shadeStyle.right"></div>

      <div class="crop-box" :style="boxStyle" @pointerdown="startDrag('move', $event)">
        <span
          v-for="handle in handles"
          :key="handle"
          class="crop-handle"
          :class="`crop-handle--${handle}`"
          @pointerdown.stop="startDrag(handle, $event)"
        ></span>
      </div>
    </div>

    <p class="crop-readout">
      <span>{{ pixelWidth }} × {{ pixelHeight }} px</span>
      <span class="crop-readout__muted">
        offset {{ pixelX }}, {{ pixelY }} of {{ sourceWidth }} × {{ sourceHeight }}
      </span>
    </p>
  </div>
</template>

<script lang="ts" setup>
import { computed, ref } from 'vue';
import { MIN_CROP_PIXELS, type CropRect } from '../lib/crop';

type Handle = 'move' | 'nw' | 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w';

const props = defineProps<{
  src: string;
  modelValue: CropRect;
  sourceWidth: number;
  sourceHeight: number;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: CropRect): void;
}>();

const handles: Handle[] =['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'];

const stageRef = ref<HTMLElement | null>(null);
const dragging = ref<Handle | null>(null);
let dragOrigin = { pointerX: 0, pointerY: 0, rect: { x: 0, y: 0, width: 1, height: 1 } };

const minWidth = computed(() =>
  props.sourceWidth > 0 ? Math.min(MIN_CROP_PIXELS / props.sourceWidth, 1) : 0.01,
);
const minHeight = computed(() =>
  props.sourceHeight > 0 ? Math.min(MIN_CROP_PIXELS / props.sourceHeight, 1) : 0.01,
);

const pixelX = computed(() => Math.round(props.modelValue.x * props.sourceWidth));
const pixelY = computed(() => Math.round(props.modelValue.y * props.sourceHeight));
const pixelWidth = computed(() => Math.round(props.modelValue.width * props.sourceWidth));
const pixelHeight = computed(() => Math.round(props.modelValue.height * props.sourceHeight));

const boxStyle = computed(() => ({
  left: `${props.modelValue.x * 100}%`,
  top: `${props.modelValue.y * 100}%`,
  width: `${props.modelValue.width * 100}%`,
  height: `${props.modelValue.height * 100}%`,
}));

const shadeStyle = computed(() => {
  const { x, y, width, height } = props.modelValue;
  const topPct = y * 100;
  const bottomPct = (1 - (y + height)) * 100;
  return {
    top: { left: '0%', top: '0%', width: '100%', height: `${topPct}%` },
    bottom: { left: '0%', bottom: '0%', width: '100%', height: `${bottomPct}%` },
    left: { left: '0%', top: `${topPct}%`, width: `${x * 100}%`, bottom: `${bottomPct}%` },
    right: {
      right: '0%',
      top: `${topPct}%`,
      width: `${(1 - (x + width)) * 100}%`,
      bottom: `${bottomPct}%`,
    },
  };
});

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function startDrag(handle: Handle, event: PointerEvent): void {
  if (!stageRef.value) return;
  event.preventDefault();
  dragging.value = handle;
  dragOrigin = {
    pointerX: event.clientX,
    pointerY: event.clientY,
    rect: { ...props.modelValue },
  };
  (event.target as HTMLElement).setPointerCapture?.(event.pointerId);
  document.addEventListener('pointermove', onDrag);
  document.addEventListener('pointerup', stopDrag);
  document.addEventListener('pointercancel', stopDrag);
}

function onDrag(event: PointerEvent): void {
  const handle = dragging.value;
  const stage = stageRef.value;
  if (!handle || !stage) return;

  const bounds = stage.getBoundingClientRect();
  if (bounds.width <= 0 || bounds.height <= 0) return;

  const dx = (event.clientX - dragOrigin.pointerX) / bounds.width;
  const dy = (event.clientY - dragOrigin.pointerY) / bounds.height;
  const origin = dragOrigin.rect;

  if (handle === 'move') {
    emit('update:modelValue', {
      ...origin,
      x: clamp(origin.x + dx, 0, 1 - origin.width),
      y: clamp(origin.y + dy, 0, 1 - origin.height),
    });
    return;
  }

  // Work in edge coordinates so opposite edges stay pinned while resizing
  let left = origin.x;
  let top = origin.y;
  let right = origin.x + origin.width;
  let bottom = origin.y + origin.height;

  if (handle.includes('w')) {
    left = clamp(origin.x + dx, 0, right - minWidth.value);
  }
  if (handle.includes('e')) {
    right = clamp(right + dx, left + minWidth.value, 1);
  }
  if (handle.includes('n')) {
    top = clamp(origin.y + dy, 0, bottom - minHeight.value);
  }
  if (handle.includes('s')) {
    bottom = clamp(bottom + dy, top + minHeight.value, 1);
  }

  emit('update:modelValue', {
    x: left,
    y: top,
    width: right - left,
    height: bottom - top,
  });
}

function stopDrag(): void {
  dragging.value = null;
  document.removeEventListener('pointermove', onDrag);
  document.removeEventListener('pointerup', stopDrag);
  document.removeEventListener('pointercancel', stopDrag);
}
</script>

<style scoped>
.crop-selector {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.crop-stage {
  position: relative;
  width: 100%;
  line-height: 0;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--border, #dfe3ec);
  background: #0f172a;
  user-select: none;
  touch-action: none;
}

.crop-image {
  width: 100%;
  height: auto;
  display: block;
  pointer-events: none;
}

.crop-shade {
  position: absolute;
  background: rgba(15, 23, 42, 0.55);
  pointer-events: none;
}

.crop-box {
  position: absolute;
  border: 2px solid var(--accent, #2563eb);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.5) inset;
  cursor: move;
}

.crop-handle {
  position: absolute;
  width: 12px;
  height: 12px;
  background: var(--surface, #ffffff);
  border: 2px solid var(--accent, #2563eb);
  border-radius: 3px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
}

.crop-handle--nw { top: -7px; left: -7px; cursor: nwse-resize; }
.crop-handle--n { top: -7px; left: 50%; transform: translateX(-50%); cursor: ns-resize; }
.crop-handle--ne { top: -7px; right: -7px; cursor: nesw-resize; }
.crop-handle--e { top: 50%; right: -7px; transform: translateY(-50%); cursor: ew-resize; }
.crop-handle--se { bottom: -7px; right: -7px; cursor: nwse-resize; }
.crop-handle--s { bottom: -7px; left: 50%; transform: translateX(-50%); cursor: ns-resize; }
.crop-handle--sw { bottom: -7px; left: -7px; cursor: nesw-resize; }
.crop-handle--w { top: 50%; left: -7px; transform: translateY(-50%); cursor: ew-resize; }

.crop-readout {
  margin: 0;
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text, #0f172a);
}

.crop-readout__muted {
  font-weight: 500;
  color: var(--muted, #6b7280);
}
</style>
