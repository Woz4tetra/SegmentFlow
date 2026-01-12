<template>
  <section class="labels-page">
    <h2>Label Editor</h2>
    <div class="controls">
      <div class="spacer" />
      <button class="btn btn-muted" @click="refreshLabels">Refresh</button>
      <button class="btn btn-primary" @click="addLabel">+ New Label</button>
    </div>

    <div v-if="labelsStore.loading" class="status">Loading labels…</div>
    <div v-else-if="labelsStore.error" class="error">{{ labelsStore.error }}</div>

    <table class="labels">
      <thead>
        <tr>
          <th style="width:36px">Color</th>
          <th>Name</th>
          <th style="width:140px">Thumbnail</th>
          <th style="width:220px">Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="lab in labelsStore.labels" :key="lab.id">
          <td>
            <button class="color-btn" :style="{ background: lab.color_hex }" title="Edit Color" @click="openPicker(lab)" />
          </td>
          <td>
            <input class="text-input" :value="lab.name" @change="(e: any) => renameLabel(lab, e.target.value)" />
          </td>
          <td>
            <div class="thumb">
              <img v-if="lab.thumbnail_path" :src="`${lab.thumbnail_path}?t=${Date.now()}`" alt="Thumbnail" />
              <span v-else class="placeholder">No thumbnail</span>
            </div>
          </td>
          <td>
            <label class="btn btn-muted file-btn">
              <input type="file" accept="image/png,image/jpeg" @change="(e: any) => onThumbUpload(lab, e)" />
              Upload Thumbnail
            </label>
          </td>
        </tr>
      </tbody>
    </table>

    <ColorPicker :modelValue="pickerColor" :open="pickerOpen" @update:modelValue="applyPicked" @close="pickerOpen=false" />
  </section>
</template>

<script lang="ts" setup>
import { ref, onMounted } from 'vue';
import { useLabelsStore, parseColorInput } from '../stores/labels';
import ColorPicker from '../components/ColorPicker.vue';

const labelsStore = useLabelsStore();

const pickerOpen = ref(false);
const pickerColor = ref<string>('#FFFFFF');
let pickerTargetId: string | null = null;

onMounted(async () => {
  await labelsStore.listLabels();
});

async function refreshLabels() { await labelsStore.listLabels(); }

async function addLabel() {
  const base = 'Label ';
  const nums = labelsStore.labels
    .map((l) => l.name)
    .map((n) => {
      const m = n.match(/^Label\s+(\d+)$/);
      return m ? Number(m[1]) : null;
    })
    .filter((n): n is number => n !== null);
  const next = nums.length ? Math.max(...nums) + 1 : labelsStore.labels.length + 1;
  const name = `${base}${next}`;
  await labelsStore.createLabel(name);
}

async function renameLabel(lab: any, name: string) {
  const n = name.trim();
  if (!n || n === lab.name) return;
  await labelsStore.updateLabel(lab.id, { name: n });
}

function openPicker(lab: any) {
  pickerColor.value = lab.color_hex;
  pickerTargetId = lab.id;
  pickerOpen.value = true;
}

async function applyPicked(hex: string) {
  pickerOpen.value = false;
  const parsed = parseColorInput(hex);
  if (!parsed || !pickerTargetId) return;
  await labelsStore.updateLabel(pickerTargetId, { color_hex: parsed });
}

async function onThumbUpload(lab: any, e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  console.log(`Uploading thumbnail for label ${lab.id}...`);
  const result = await labelsStore.uploadThumbnail(lab.id, file);
  if (result) {
    console.log('Thumbnail uploaded successfully:', result);
    input.value = '';
  } else {
    console.error('Thumbnail upload failed:', labelsStore.error);
  }
}
</script>

<style scoped>
.labels-page { display: flex; flex-direction: column; gap: 1rem; }
.controls { display: flex; gap: 0.6rem; align-items: center; justify-content: flex-end; }
.spacer { flex: 1; }
.btn { border: 1px solid var(--border,#dfe3ec); border-radius: 10px; padding: 0.45rem 0.8rem; cursor: pointer; transition: background var(--transition-duration,.2s), box-shadow var(--transition-duration,.2s); color: var(--text,#0f172a); }
.btn-muted { background: var(--surface-muted,#eef2f7); color: var(--text,#0f172a); }
.btn-primary { background: linear-gradient(135deg, #6f7bf7, #8f5cf7); color: white; border: none; box-shadow: 0 8px 24px rgba(143, 92, 247, .25); }
.btn:hover { box-shadow: 0 8px 24px rgba(0,0,0,.06); }
.status { color: #64748B; }
.error { color: #EF4444; }
.table-actions { display: flex; gap: 0.4rem; }
.labels { width: 100%; border-collapse: collapse; }
.labels th, .labels td { border-bottom: 1px solid var(--border,#e5e7eb); padding: 0.4rem; }
.color-btn { width: 24px; height: 24px; border-radius: 6px; border: 1px solid rgba(0,0,0,0.1); cursor: pointer; }
.text-input { width: 100%; font-family: var(--font); font-size: 0.95rem; line-height: 1.25rem; padding: 0.45rem 0.6rem; border: 1px solid var(--border,#dfe3ec); border-radius: 10px; background: var(--surface,#fff); color: var(--text,#0f172a); transition: box-shadow var(--transition-duration,.2s), border-color var(--transition-duration,.2s); }
.text-input:focus { outline: none; box-shadow: 0 8px 24px rgba(0,0,0,.06); border-color: #c9cfe0; }
.thumb { width: 120px; height: 60px; display: grid; place-items: center; border: 1px dashed var(--border,#dfe3ec); border-radius: 8px; overflow: hidden; }
.thumb img { width: 100%; height: 100%; object-fit: cover; }
.placeholder { color: #64748B; font-size: 0.85rem; }
.file-btn input { display: none; }
</style>
