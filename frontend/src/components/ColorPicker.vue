<template>
  <div v-show="open" class="overlay" @click.self="close">
    <div class="panel">
      <header class="header">
        <strong>Pick Color</strong>
        <button class="close" @click="close" title="Close">✕</button>
      </header>
      <div class="content">
        <div class="palette" aria-label="Preset Colors">
          <button
            v-for="hex in gridPalette"
            :key="hex"
            :style="{ background: hex }"
            class="swatch"
            @click="applyColor(hex)"
          />
        </div>
        <div class="picker-wrapper">
          <div ref="wheelEl" class="picker picker--wheel" aria-label="Hue Wheel"></div>
          <div ref="boxEl" class="picker picker--box" aria-label="Saturation/Value"></div>
        </div>
      </div>
      <div class="inputs">
        <input class="text-input" v-model="text" placeholder="#RRGGBB / rgb(…) / named" @change="onTextChange" />
      </div>
      <footer class="footer">
        <button class="apply" @click="applyCurrent">Apply</button>
      </footer>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { onMounted, onUnmounted, ref, watch } from 'vue';
import iro from '@jaames/iro';
import { parseColorInput } from '../stores/labels';

const props = defineProps<{ modelValue: string; open: boolean }>();
const emit = defineEmits<{ (e: 'update:modelValue', v: string): void; (e: 'close'): void }>();

const wheelEl = ref<HTMLElement | null>(null);
const boxEl = ref<HTMLElement | null>(null);
const wheelPicker = ref<any>(null);
const boxPicker = ref<any>(null);
const text = ref(props.modelValue ?? '#FFFFFF');
const open = ref(props.open);
const gridPalette = ref<string[]>(generateGridPalette());

watch(() => props.open, (v) => { open.value = v; });
watch(() => props.modelValue, (v) => {
  text.value = v ?? '#FFFFFF';
  if (wheelPicker.value) wheelPicker.value.color.hexString = text.value;
  if (boxPicker.value) boxPicker.value.color.hexString = text.value;
});

function close() { emit('close'); }
function applyColor(hex: string) {
  text.value = hex;
  if (wheelPicker.value) wheelPicker.value.color.hexString = hex;
  if (boxPicker.value) boxPicker.value.color.hexString = hex;
}
function applyCurrent() { emit('update:modelValue', text.value); close(); }
function onTextChange() { const parsed = parseColorInput(text.value); if (parsed) applyColor(parsed); }

onMounted(() => {
  const IroColorPicker = (iro as any).ColorPicker;
  if (wheelEl.value) {
    wheelPicker.value = new IroColorPicker(wheelEl.value, {
      width: 240,
      color: text.value,
      layout: [ { component: iro.ui.Wheel } ],
    });
    wheelPicker.value.on('color:change', (color: any) => {
      text.value = color.hexString;
      if (boxPicker.value) boxPicker.value.color.hexString = color.hexString;
    });
  }
  if (boxEl.value) {
    boxPicker.value = new IroColorPicker(boxEl.value, {
      width: 240,
      color: text.value,
      layout: [
        { component: iro.ui.Box },
        { component: iro.ui.Slider, options: { sliderType: 'value' } },
        { component: iro.ui.Slider, options: { sliderType: 'saturation' } },
      ],
    });
    boxPicker.value.on('color:change', (color: any) => {
      text.value = color.hexString;
      if (wheelPicker.value) wheelPicker.value.color.hexString = color.hexString;
    });
  }
});

onUnmounted(() => { wheelPicker.value = null; boxPicker.value = null; });

function hslToHex(h: number, s: number, l: number): string {
  s /= 100; l /= 100;
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  let r = 0, g = 0, b = 0;
  if (h >= 0 && h < 60) { r = c; g = x; b = 0; }
  else if (h < 120) { r = x; g = c; b = 0; }
  else if (h < 180) { r = 0; g = c; b = x; }
  else if (h < 240) { r = 0; g = x; b = c; }
  else if (h < 300) { r = x; g = 0; b = c; }
  else { r = c; g = 0; b = x; }
  const to255 = (v: number) => Math.round((v + m) * 255);
  const hex = (n: number) => n.toString(16).padStart(2, '0').toUpperCase();
  return `#${hex(to255(r))}${hex(to255(g))}${hex(to255(b))}`;
}

function generateGridPalette(): string[] {
  const colors: string[] = [];
  const hues = Array.from({ length: 10 }, (_, i) => i * 36); // 0..324
  const lightnessLevels = Array.from({ length: 10 }, (_, i) => 35 + i * 5); // 35..80
  const saturation = 82; // vibrant
  for (const l of lightnessLevels) {
    for (const h of hues) {
      colors.push(hslToHex(h, saturation, l));
    }
  }
  return colors;
}
</script>

<style scoped>
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.35); display: grid; place-items: center; z-index: 50; }
.panel { width: 900px; max-width: 98vw; background: var(--surface, #fff); border: 1px solid var(--border, #dfe3ec); border-radius: 12px; box-shadow: 0 12px 36px rgba(0,0,0,0.12); padding: 0.75rem; }
.header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem; }
.close { border: none; background: transparent; cursor: pointer; font-size: 1rem; }
.content { display: grid; grid-template-columns: 360px 520px; gap: 1rem; align-items: start; }
.picker-wrapper { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem; align-items: start; justify-items: center; }
.picker { margin: 0.25rem 0 0.5rem; }
.inputs { display: flex; flex-direction: column; gap: 0.5rem; }
.text-input { width: 100%; font-family: var(--font); font-size: 0.95rem; line-height: 1.25rem; padding: 0.45rem 0.6rem; border: 1px solid var(--border,#dfe3ec); border-radius: 10px; background: var(--surface,#fff); color: var(--text,#0f172a); transition: box-shadow var(--transition-duration,.2s), border-color var(--transition-duration,.2s); }
.text-input:focus { outline: none; box-shadow: 0 8px 24px rgba(0,0,0,.06); border-color: #c9cfe0; }
.palette { display: grid; grid-template-columns: repeat(10, 1fr); grid-auto-rows: 24px; gap: 0.25rem; }
.swatch { width: 100%; height: 100%; border-radius: 6px; border: 1px solid rgba(0,0,0,0.1); cursor: pointer; }
.footer { display: flex; justify-content: flex-end; margin-top: 0.6rem; }
.apply { border: 1px solid var(--border,#dfe3ec); background: var(--surface-muted,#eef2f7); border-radius: 8px; padding: 0.4rem 0.8rem; cursor: pointer; }
</style>
