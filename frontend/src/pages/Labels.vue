<template>
  <section class="labels-page">
    <h2>Label Editor</h2>
    <div class="controls">
      <label>
        Project:
        <select v-model="selectedProjectId" @change="onProjectChange">
          <option :value="''" disabled>Select a project</option>
          <option v-for="p in projectsStore.activeProjects" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
      </label>
      <button class="refresh" @click="refreshLabels" :disabled="!selectedProjectId">Reload Labels</button>
      <button class="add" @click="addLabel" :disabled="!selectedProjectId">Add Label</button>
    </div>

    <div v-if="labelsStore.loading" class="status">Loading labels…</div>
    <div v-else-if="labelsStore.error" class="error">{{ labelsStore.error }}</div>

    <table v-if="selectedProjectId" class="labels">
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
            <input :value="lab.name" @change="(e: any) => renameLabel(lab, e.target.value)" />
          </td>
          <td>
            <div class="thumb">
              <img v-if="lab.thumbnail_path" :src="lab.thumbnail_path" alt="Thumbnail" />
              <span v-else class="placeholder">No thumbnail</span>
            </div>
          </td>
          <td>
            <label class="upload">
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
import { useProjectsStore } from '../stores/projects';
import { useLabelsStore, parseColorInput } from '../stores/labels';
import ColorPicker from '../components/ColorPicker.vue';

const projectsStore = useProjectsStore();
const labelsStore = useLabelsStore();

const selectedProjectId = ref<string>('');
const pickerOpen = ref(false);
const pickerColor = ref<string>('#FFFFFF');
let pickerTargetId: string | null = null;

onMounted(async () => {
  if (!projectsStore.projects.length) await projectsStore.fetchProjects();
});

async function onProjectChange() {
  if (selectedProjectId.value) await labelsStore.listLabels(selectedProjectId.value);
}
async function refreshLabels() { if (selectedProjectId.value) await labelsStore.listLabels(selectedProjectId.value); }

async function addLabel() {
  const name = prompt('New label name:')?.trim();
  if (!name) return;
  await labelsStore.createLabel(selectedProjectId.value, name);
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
  await labelsStore.uploadThumbnail(lab.id, file);
  input.value = '';
}
</script>

<style scoped>
.labels-page { display: flex; flex-direction: column; gap: 1rem; }
.controls { display: flex; gap: 0.6rem; align-items: center; }
.controls select { border: 1px solid var(--border,#dfe3ec); border-radius: 8px; padding: 0.3rem 0.5rem; }
.controls .add, .controls .refresh { border: 1px solid var(--border,#dfe3ec); background: var(--surface-muted,#eef2f7); border-radius: 8px; padding: 0.3rem 0.6rem; cursor: pointer; }
.status { color: #64748B; }
.error { color: #EF4444; }
.table-actions { display: flex; gap: 0.4rem; }
.labels { width: 100%; border-collapse: collapse; }
.labels th, .labels td { border-bottom: 1px solid var(--border,#e5e7eb); padding: 0.4rem; }
.color-btn { width: 24px; height: 24px; border-radius: 6px; border: 1px solid rgba(0,0,0,0.1); cursor: pointer; }
.thumb { width: 120px; height: 60px; display: grid; place-items: center; border: 1px dashed var(--border,#dfe3ec); border-radius: 8px; overflow: hidden; }
.thumb img { width: 100%; height: 100%; object-fit: cover; }
.placeholder { color: #64748B; font-size: 0.85rem; }
.upload input { display: none; }
.upload { border: 1px solid var(--border,#dfe3ec); background: var(--surface-muted,#eef2f7); border-radius: 8px; padding: 0.3rem 0.6rem; cursor: pointer; }
</style>
