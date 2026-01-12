<template>
  <div class="dual-slider" ref="sliderRef">
    <div class="track"></div>
    <div class="range" :style="rangeStyle"></div>
    <div
      class="thumb thumb-start"
      :style="{ left: startPercent + '%' }"
      @mousedown="startDrag('start', $event)"
      @touchstart.prevent="startDrag('start', $event)"
    ></div>
    <div
      class="thumb thumb-end"
      :style="{ left: endPercent + '%' }"
      @mousedown="startDrag('end', $event)"
      @touchstart.prevent="startDrag('end', $event)"
    ></div>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';

const props = defineProps<{
  min: number;
  max: number;
  startValue: number;
  endValue: number;
  step?: number;
}>();

const emit = defineEmits<{
  (e: 'update:startValue', value: number): void;
  (e: 'update:endValue', value: number): void;
  (e: 'change'): void;
}>();

const sliderRef = ref<HTMLElement | null>(null);
const dragging = ref<'start' | 'end' | null>(null);

const step = computed(() => props.step ?? 0.1);

const startPercent = computed(() => {
  if (props.max <= props.min) return 0;
  return ((props.startValue - props.min) / (props.max - props.min)) * 100;
});

const endPercent = computed(() => {
  if (props.max <= props.min) return 100;
  return ((props.endValue - props.min) / (props.max - props.min)) * 100;
});

const rangeStyle = computed(() => ({
  left: startPercent.value + '%',
  width: (endPercent.value - startPercent.value) + '%',
}));

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function roundToStep(value: number): number {
  const s = step.value;
  return Math.round(value / s) * s;
}

function getValueFromEvent(e: MouseEvent | TouchEvent): number {
  if (!sliderRef.value) return props.min;
  const rect = sliderRef.value.getBoundingClientRect();
  const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
  const percent = clamp((clientX - rect.left) / rect.width, 0, 1);
  const rawValue = props.min + percent * (props.max - props.min);
  return roundToStep(rawValue);
}

function startDrag(which: 'start' | 'end', e: MouseEvent | TouchEvent) {
  dragging.value = which;
  document.addEventListener('mousemove', onDrag);
  document.addEventListener('mouseup', stopDrag);
  document.addEventListener('touchmove', onDrag);
  document.addEventListener('touchend', stopDrag);
}

function onDrag(e: MouseEvent | TouchEvent) {
  if (!dragging.value) return;
  const value = getValueFromEvent(e);
  
  if (dragging.value === 'start') {
    // Start can't go past end
    const clamped = clamp(value, props.min, props.endValue - step.value);
    emit('update:startValue', clamped);
  } else {
    // End can't go before start
    const clamped = clamp(value, props.startValue + step.value, props.max);
    emit('update:endValue', clamped);
  }
}

function stopDrag() {
  const wasDragging = dragging.value !== null;
  dragging.value = null;
  document.removeEventListener('mousemove', onDrag);
  document.removeEventListener('mouseup', stopDrag);
  if (wasDragging) {
    emit('change');
  }
  document.removeEventListener('touchmove', onDrag);
  document.removeEventListener('touchend', stopDrag);
}

onUnmounted(() => {
  stopDrag();
});
</script>

<style scoped>
.dual-slider {
  position: relative;
  width: 100%;
  height: 24px;
  user-select: none;
  touch-action: none;
}

.track {
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 6px;
  transform: translateY(-50%);
  background: var(--border, #dfe3ec);
  border-radius: 3px;
}

.range {
  position: absolute;
  top: 50%;
  height: 6px;
  transform: translateY(-50%);
  background: var(--accent, #2563eb);
  border-radius: 3px;
}

.thumb {
  position: absolute;
  top: 50%;
  width: 20px;
  height: 20px;
  transform: translate(-50%, -50%);
  background: var(--surface, #ffffff);
  border: 3px solid var(--accent, #2563eb);
  border-radius: 50%;
  cursor: grab;
  transition: box-shadow 0.15s ease, transform 0.1s ease;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}

.thumb:hover {
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.2);
  transform: translate(-50%, -50%) scale(1.1);
}

.thumb:active {
  cursor: grabbing;
  transform: translate(-50%, -50%) scale(1.15);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
}
</style>
