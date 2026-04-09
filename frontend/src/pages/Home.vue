<template>
  <section class="hero">
    <div class="hero__text">
      <p class="eyebrow">Projects</p>
      <h1>Annotation Projects</h1>
      <p class="lede">
        Create a new project and upload a video, or upload a video to an existing project to continue annotation.
      </p>
      <div class="hero__meta">
        <span class="pill">{{ total }} projects</span>
      </div>
    </div>
    <div class="hero__actions">
      <button
        :class="['ghost', { 'ghost--active': bulkMode }]"
        type="button"
        @click="toggleBulkMode"
      >
        {{ bulkMode ? 'Exit Bulk' : 'Bulk Actions' }}
      </button>
      <button class="ghost" type="button" :disabled="loading" @click="handleRefresh">
        {{ loading ? 'Refreshing...' : 'Refresh' }}
      </button>
      <button class="primary" type="button" @click="handleCreateProject">
        + New Project
      </button>
    </div>
  </section>

  <!-- Bulk Actions Toolbar -->
  <div v-if="bulkMode && orderedProjects.length" class="bulk-toolbar">
    <div class="bulk-toolbar__left">
      <label class="bulk-select-all" @click.prevent="toggleSelectAll">
        <input
          type="checkbox"
          :checked="allSelected"
          :indeterminate.prop="selectedCount > 0 && !allSelected"
        />
        <span v-if="allSelected">Deselect All</span>
        <span v-else>Select All</span>
      </label>
      <span class="bulk-count">{{ selectedCount }} selected</span>
    </div>
    <div class="bulk-toolbar__right">
      <div class="bulk-dropdown" @click.stop>
        <button
          class="bulk-dropdown__trigger"
          type="button"
          :disabled="selectedCount === 0 || bulkBusy"
          @click="bulkDropdownOpen = !bulkDropdownOpen"
        >
          {{ bulkBusy ? 'Working...' : 'Run Action' }}
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M6 9l6 6 6-6"/>
          </svg>
        </button>
        <div v-if="bulkDropdownOpen" class="bulk-dropdown__menu">
          <button
            v-for="action in bulkActions"
            :key="action.key"
            class="bulk-dropdown__item"
            type="button"
            @click="runBulkAction(action.key)"
          >
            {{ action.label }}
          </button>
        </div>
      </div>
    </div>
  </div>
  <div v-if="bulkResultMessage" class="bulk-result" :data-tone="bulkResultTone">
    {{ bulkResultMessage }}
  </div>

  <section class="content">
    <div v-if="loading" class="grid">
      <article v-for="i in 6" :key="i" class="project-card project-card--skeleton">
        <div class="thumb skeleton-block"></div>
        <div class="meta skeleton-block"></div>
        <div class="meta skeleton-block"></div>
      </article>
    </div>

    <div v-else-if="error" class="empty">
      <div>
        <p class="empty__title">Could not load projects</p>
        <p class="empty__body">{{ error }}</p>
        <button class="ghost" type="button" @click="handleRefresh">Retry</button>
      </div>
    </div>

    <div v-else-if="!orderedProjects.length" class="empty">
      <div>
        <p class="empty__title">No projects yet</p>
        <p class="empty__body">Click "New Project" to create your first project, then upload a video to begin annotation.</p>
      </div>
    </div>

    <div v-else class="grid">
      <article
        v-for="project in orderedProjects"
        :key="project.id"
        :class="['project-card', { 'project-card--selected': bulkMode && selectedIds.has(project.id) }]"
        :data-available="isStageAvailable(effectiveStage(project))"
        role="button"
        tabindex="0"
        :title="bulkMode ? 'Toggle selection' : isStageAvailable(effectiveStage(project)) ? 'Open editor' : 'Editor coming soon for this stage'"
        @click="bulkMode ? toggleProjectSelection(project.id) : goToStage(project)"
        @keydown.enter="bulkMode ? toggleProjectSelection(project.id) : goToStage(project)"
      >
        <div class="thumb" :style="project.video_path ? {} : gradientStyle(project)">
          <img
            v-if="project.video_path"
            :src="getThumbnailUrl(project.id)"
            alt=""
            class="thumb__img"
            @error="onThumbnailError"
          />
          <!-- Bulk selection checkbox -->
          <div v-if="bulkMode" class="bulk-check" @click.stop="toggleProjectSelection(project.id)">
            <input type="checkbox" :checked="selectedIds.has(project.id)" tabindex="-1" />
          </div>
          <div class="thumb__top">
            <div class="thumb__badges">
            <span
              class="stage"
              :data-tone="toneForStage(effectiveStage(project))"
            >
              {{ labelForStage(effectiveStage(project)) }}
            </span>
            <span class="status" :data-active="project.active">
              {{ project.active ? 'Active' : 'Archived' }}
            </span>
            </div>
            <div class="card-menu" @click.stop>
              <button
                class="menu-trigger"
                type="button"
                aria-label="Project actions"
                @click.stop="toggleMenu(project.id)"
              >
                ...
              </button>
              <div v-if="openMenuId === project.id" class="menu-panel">
                <button class="menu-item menu-item--danger" type="button" @click.stop="promptDelete(project)">
                  Delete project
                </button>
              </div>
            </div>
          </div>
          <div class="thumb__name">{{ project.name }}</div>
        </div>

        <div class="meta">
          <div v-if="visible_columns.created" class="meta__row">
            <span>Created</span>
            <strong>{{ formatDate(project.created_at) }}</strong>
          </div>
          <div v-if="visible_columns.updated" class="meta__row">
            <span>Updated</span>
            <strong>{{ formatDate(project.updated_at) }}</strong>
          </div>
          <div v-if="visible_columns.video && project.video_path" class="meta__row" title="Video path">
            <span>Video</span>
            <strong class="truncate">{{ displayVideoName(project.video_path) }}</strong>
          </div>
        </div>
      </article>
    </div>
  </section>

  <div v-if="deleteTarget" class="modal-overlay" @click.self="closeDeleteModal">
    <div class="modal-dialog">
      <h3>Delete project?</h3>
      <p>
        This will permanently remove
        <strong>{{ deleteTarget.name }}</strong>
        and all associated frames and labels for this project.
      </p>
      <p v-if="deleteError" class="modal-error">{{ deleteError }}</p>
      <div class="modal-actions">
        <button class="btn-cancel" type="button" :disabled="deleteBusy" @click="closeDeleteModal">
          Cancel
        </button>
        <button class="btn-confirm-delete" type="button" :disabled="deleteBusy" @click="confirmDelete">
          {{ deleteBusy ? 'Deleting...' : 'Delete project' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { storeToRefs } from 'pinia';
import type { Project, ProjectStage } from '../stores/projects';
import { useProjectsStore } from '../stores/projects';
import { useUserSettingsStore } from '../stores/userSettings';
import { useRouter } from 'vue-router';
import { API_BASE_URL, buildApiUrl } from '../lib/api';

const projectsStore = useProjectsStore();
const { projects, total, loading, error } = storeToRefs(projectsStore);
const { fetchProjects, deleteProject, startPropagation, clearPropagatedFrames } = projectsStore;

const userSettingsStore = useUserSettingsStore();
const { visible_columns } = storeToRefs(userSettingsStore);

const router = useRouter();

const stageMeta: Record<ProjectStage, { label: string; tone: 'info' | 'warn' | 'success' | 'accent' }> = {
  upload: { label: 'Stage 0 / Upload', tone: 'accent' },
  trim: { label: 'Stage 1 / Trim', tone: 'info' },
  manual_labeling: { label: 'Stage 2 / Labeling', tone: 'accent' },
  propagation: { label: 'Stage 3 / Propagation', tone: 'info' },
  validation: { label: 'Stage 4 / Validation', tone: 'warn' },
  export: { label: 'Stage 5 / Export', tone: 'success' },
};

const palette: Array<[string, string]> = [
  ['#0ea5e9', '#6366f1'],
  ['#2563eb', '#1d4ed8'],
  ['#22c55e', '#16a34a'],
  ['#f97316', '#ea580c'],
  ['#a855f7', '#6b21a8'],
  ['#14b8a6', '#0f766e'],
  ['#f59e0b', '#d97706'],
];

const orderedProjects = computed<Project[]>(() =>
  [...projects.value].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  ),
);

const formatDate = (value?: string): string => {
  if (!value) return '—';
  const date = new Date(value);
  return new Intl.DateTimeFormat('en', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
};

const hashSeed = (seed?: string): number => {
  const s = (seed ?? 'segmentflow').toString();
  return s.split('').reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
};

const gradientStyle = (project: Project) => {
  const seed = project?.id ?? project?.name ?? 'segmentflow';
  const idx = Math.abs(hashSeed(seed)) % palette.length;
  const [from, to] = palette[idx];
  return { background: `linear-gradient(135deg, ${from}, ${to})` };
};

const baseApi = API_BASE_URL;

const getThumbnailUrl = (projectId: string): string => {
  return `${baseApi}/projects/${projectId}/thumbnail`;
};

const onThumbnailError = (e: Event) => {
  // Hide broken image, gradient fallback will show
  const img = e.target as HTMLImageElement;
  img.style.display = 'none';
};

const labelForStage = (stage: ProjectStage): string => stageMeta[stage]?.label ?? 'Unknown stage';
const toneForStage = (stage: ProjectStage): string => stageMeta[stage]?.tone ?? 'info';

// Derive effective stage: if a video exists but stage is still 'upload', treat as 'trim'
const effectiveStage = (project: Project): ProjectStage => {
  if (project.stage === 'upload' && project.video_path) return 'trim';
  return project.stage;
};

const isStageAvailable = (stage: ProjectStage): boolean => 
  stage === 'upload' ||
  stage === 'trim' ||
  stage === 'manual_labeling' ||
  stage === 'propagation' ||
  stage === 'validation' ||
  stage === 'export';

const routeForProject = (project: Project) => {
  const eff = effectiveStage(project);
  if (eff === 'upload' && project.id) {
    return { name: 'Upload', params: { id: project.id } };
  }
  if (eff === 'trim' && project.id) {
    return { name: 'Trim', params: { id: project.id } };
  }
  if (eff === 'manual_labeling' && project.id) {
    return { name: 'ManualLabeling', params: { id: project.id } };
  }
  if (eff === 'propagation' && project.id) {
    return { name: 'Propagation', params: { id: project.id } };
  }
  if (eff === 'validation' && project.id) {
    return { name: 'Validation', params: { id: project.id } };
  }
  if (eff === 'export' && project.id) {
    return { name: 'Export', params: { id: project.id } };
  }
  return null;
};

const goToStage = (project: Project) => {
  const route = routeForProject(project);
  if (route) {
    router.push(route);
  }
};

const handleRefresh = async () => {
  await fetchProjects();
};

const handleCreateProject = () => {
  router.push({ name: 'Upload', params: { id: 'new' } });
};

const openMenuId = ref<string | null>(null);
const deleteTarget = ref<Project | null>(null);
const deleteBusy = ref(false);
const deleteError = ref('');

const displayVideoName = (path?: string | null): string => {
  if (!path) return '—';
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1] || path;
};

const toggleMenu = (projectId: string) => {
  openMenuId.value = openMenuId.value === projectId ? null : projectId;
};

const closeMenu = () => {
  openMenuId.value = null;
};

const promptDelete = (project: Project) => {
  deleteTarget.value = project;
  deleteError.value = '';
  closeMenu();
};

const closeDeleteModal = () => {
  if (deleteBusy.value) return;
  deleteTarget.value = null;
  deleteError.value = '';
};

const confirmDelete = async () => {
  if (!deleteTarget.value || deleteBusy.value) return;
  deleteBusy.value = true;
  deleteError.value = '';
  const success = await deleteProject(deleteTarget.value.id);
  deleteBusy.value = false;
  if (success) {
    deleteTarget.value = null;
  } else {
    deleteError.value = projectsStore.error || 'Failed to delete project';
  }
};

// ── Bulk Actions ──
const bulkMode = ref(false);
const selectedIds = ref<Set<string>>(new Set());
const bulkDropdownOpen = ref(false);
const bulkBusy = ref(false);
const bulkResultMessage = ref('');
const bulkResultTone = ref<'success' | 'warning'>('success');

const selectedCount = computed(() => selectedIds.value.size);
const allSelected = computed(() =>
  orderedProjects.value.length > 0 && selectedIds.value.size === orderedProjects.value.length,
);

function toggleBulkMode(): void {
  bulkMode.value = !bulkMode.value;
  if (!bulkMode.value) {
    selectedIds.value = new Set();
    bulkDropdownOpen.value = false;
    bulkResultMessage.value = '';
  }
}

function toggleProjectSelection(id: string): void {
  const next = new Set(selectedIds.value);
  if (next.has(id)) next.delete(id); else next.add(id);
  selectedIds.value = next;
}

function selectAll(): void {
  selectedIds.value = new Set(orderedProjects.value.map(p => p.id));
}

function deselectAll(): void {
  selectedIds.value = new Set();
}

function toggleSelectAll(): void {
  if (allSelected.value) deselectAll(); else selectAll();
}

type BulkAction = 'export_yolo' | 'export_segmask' | 'start_propagation' | 'clear_propagated_frames';

const bulkActions: { key: BulkAction; label: string }[] = [
  { key: 'start_propagation', label: 'Start Propagation' },
  { key: 'clear_propagated_frames', label: 'Clear Propagated Frames' },
  { key: 'export_yolo', label: 'Export YOLO' },
  { key: 'export_segmask', label: 'Export Segmentation Masks' },
];

function actionLabel(action: BulkAction): string {
  return bulkActions.find((item) => item.key === action)?.label ?? action;
}

function triggerDownload(url: string): void {
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', '');
  link.setAttribute('rel', 'noopener');
  link.setAttribute('target', '_blank');
  document.body.appendChild(link);
  link.click();
  link.remove();
}

async function runBulkAction(action: BulkAction): Promise<void> {
  bulkDropdownOpen.value = false;
  if (selectedIds.value.size === 0 || bulkBusy.value) return;
  const selectedCountValue = selectedIds.value.size;
  const confirmed = window.confirm(
    `Are you sure you want to run "${actionLabel(action)}" on ${selectedCountValue} selected project${selectedCountValue === 1 ? '' : 's'}?`,
  );
  if (!confirmed) return;
  bulkBusy.value = true;
  bulkResultMessage.value = '';

  const ids = [...selectedIds.value];
  try {
    if (action === 'start_propagation') {
      let startedCount = 0;
      const failures: string[] = [];

      for (const id of ids) {
        const result = await startPropagation(id);
        if (result) {
          startedCount += 1;
        } else {
          failures.push(`${id.slice(0, 8)}: ${projectsStore.error || 'Failed to start propagation'}`);
        }
      }

      bulkResultTone.value = failures.length > 0 ? 'warning' : 'success';
      const failureSnippet =
        failures.length > 0
          ? ` Failed (${failures.length}): ${failures.slice(0, 3).join(' | ')}${failures.length > 3 ? ' ...' : ''}`
          : '';
      bulkResultMessage.value = `Propagation queued for ${startedCount}/${ids.length} selected projects.${failureSnippet}`;
      return;
    }

    if (action === 'clear_propagated_frames') {
      let successCount = 0;
      let totalFramesCleared = 0;
      let totalMasksDeleted = 0;
      const failures: string[] = [];

      for (const id of ids) {
        const result = await clearPropagatedFrames(id);
        if (result) {
          successCount += 1;
          totalFramesCleared += result.frames_cleared ?? 0;
          totalMasksDeleted += result.masks_deleted ?? 0;
        } else {
          failures.push(`${id.slice(0, 8)}: ${projectsStore.error || 'Failed to clear propagated frames'}`);
        }
      }

      bulkResultTone.value = failures.length > 0 ? 'warning' : 'success';
      const failureSnippet =
        failures.length > 0
          ? ` Failed (${failures.length}): ${failures.slice(0, 3).join(' | ')}${failures.length > 3 ? ' ...' : ''}`
          : '';
      bulkResultMessage.value =
        `Cleared propagated frames for ${successCount}/${ids.length} selected projects `
        + `(${totalFramesCleared} frames, ${totalMasksDeleted} masks).${failureSnippet}`;
      return;
    }

    const skipParam = userSettingsStore.export_skip_n > 1
      ? `?skip_n=${userSettingsStore.export_skip_n}`
      : '';
    const pathSegment = action === 'export_yolo' ? 'yolo' : 'segmask';

    for (let i = 0; i < ids.length; i++) {
      triggerDownload(buildApiUrl(`/projects/${ids[i]}/export/${pathSegment}${skipParam}`));
      if (i < ids.length - 1) {
        await new Promise(r => setTimeout(r, 500));
      }
    }

    bulkResultTone.value = 'success';
    bulkResultMessage.value = `Started ${ids.length} export download${ids.length === 1 ? '' : 's'}.`;
  } finally {
    bulkBusy.value = false;
  }
}

const handleGlobalClick = () => {
  if (openMenuId.value) {
    closeMenu();
  }
  if (bulkDropdownOpen.value) {
    bulkDropdownOpen.value = false;
  }
};

onMounted(() => {
  fetchProjects();
  window.addEventListener('click', handleGlobalClick);
});

onBeforeUnmount(() => {
  window.removeEventListener('click', handleGlobalClick);
});
</script>

<style scoped>
.hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.5rem;
  padding: 1.25rem 1.5rem;
  border: 1px solid var(--border, #dfe3ec);
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.06), rgba(99, 102, 241, 0.04)),
    var(--surface, #ffffff);
  border-radius: 18px;
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.06);
  margin-bottom: 1.25rem;
  width: 100%;
  transition: background var(--transition-duration, 0.2s) ease, box-shadow var(--transition-duration, 0.2s) ease, border-color var(--transition-duration, 0.2s) ease;
}

.hero__text {
  max-width: 720px;
}

.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 700;
  font-size: 0.8rem;
  color: var(--muted, #5b6474);
  margin: 0 0 0.35rem;
}

h1 {
  margin: 0 0 0.25rem;
  font-size: 2rem;
  letter-spacing: -0.02em;
}

.lede {
  margin: 0 0 0.75rem;
  color: var(--muted, #4b5563);
  line-height: 1.6;
}

.hero__meta {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 0.5rem;
}

.hero__actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.primary,
.ghost {
  padding: 0.65rem 1rem;
  border-radius: 12px;
  font-weight: 600;
  border: 1px solid transparent;
  cursor: pointer;
  transition: transform var(--transition-duration, 0.2s) ease, box-shadow var(--transition-duration, 0.2s) ease, opacity var(--transition-duration, 0.2s) ease, background var(--transition-duration, 0.2s) ease;
  font-size: 0.95rem;
}

.primary {
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: #ffffff;
  box-shadow: 0 10px 30px rgba(37, 99, 235, 0.28);
  border-color: rgba(124, 58, 237, 0.35);
}

.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  box-shadow: none;
}

.ghost {
  background: var(--surface, #ffffff);
  border-color: var(--border, #dfe3ec);
  color: var(--text, #0f172a);
  text-decoration: none;
  display: inline-block;
}

.primary:not(:disabled):hover,
.ghost:not(:disabled):hover {
  transform: translateY(-2px);
}

.pill {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.7rem;
  border-radius: 999px;
  background: var(--surface-muted, #eef2f7);
  color: var(--text, #0f172a);
  font-weight: 600;
  font-size: 0.9rem;
}

.pill--muted {
  background: var(--pill, #e2e8f0);
  color: var(--muted, #4b5563);
}

.content {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  width: 100%;
}

.grid {
  display: grid;
  gap: 1.25rem;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  width: 100%;
}

.project-card {
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
  aspect-ratio: 1;
  transition: transform var(--transition-duration, 0.2s) ease, box-shadow var(--transition-duration, 0.2s) ease, background var(--transition-duration, 0.2s) ease, border-color var(--transition-duration, 0.2s) ease;
}

.project-card[data-available='true'] {
  cursor: pointer;
}

.project-card[data-available='true']:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 36px rgba(0, 0, 0, 0.08);
}

.project-card--skeleton {
  border-style: dashed;
  border-color: var(--border, #dfe3ec);
}

.thumb {
  padding: 1rem 1.1rem;
  color: #ffffff;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  justify-content: space-between;
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, #6366f1, #2563eb);
}

.thumb__img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  z-index: 0;
}

/* Gradient overlay for text readability over thumbnails */
.thumb::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(to bottom, rgba(0,0,0,0.3) 0%, rgba(0,0,0,0.1) 40%, rgba(0,0,0,0.4) 100%);
  z-index: 0;
  pointer-events: none;
}

.thumb__top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  position: relative;
  z-index: 1;
}

.thumb__badges {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.thumb__name {
  position: relative;
  z-index: 1;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
}

.stage {
  padding: 0.3rem 0.6rem;
  border-radius: 12px;
  font-weight: 700;
  font-size: 0.85rem;
  background: rgba(0, 0, 0, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.4);
  white-space: nowrap;
}


.stage[data-tone='warn'] {
  background: rgba(255, 163, 64, 0.22);
  border-color: rgba(255, 255, 255, 0.45);
}

.stage[data-tone='success'] {
  background: rgba(34, 197, 94, 0.2);
}

.status {
  padding: 0.25rem 0.55rem;
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.26);
  font-weight: 600;
  font-size: 0.8rem;
  border: 1px solid rgba(255, 255, 255, 0.28);
}

.status[data-active='false'] {
  background: rgba(0, 0, 0, 0.5);
  opacity: 0.75;
}

.thumb__name {
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.card-menu {
  position: relative;
  z-index: 2;
}

.menu-trigger {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.35);
  background: rgba(15, 23, 42, 0.2);
  color: #ffffff;
  font-size: 1.2rem;
  font-weight: 700;
  line-height: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s ease;
}

.menu-trigger:hover {
  background: rgba(15, 23, 42, 0.35);
}

.menu-panel {
  position: absolute;
  top: 38px;
  right: 0;
  min-width: 160px;
  background: var(--surface, #ffffff);
  border-radius: 12px;
  border: 1px solid var(--border, #dfe3ec);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.18);
  padding: 0.35rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.menu-item {
  border: none;
  background: transparent;
  text-align: left;
  padding: 0.55rem 0.65rem;
  border-radius: 10px;
  font-size: 0.9rem;
  color: var(--text, #0f172a);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.menu-item:hover {
  background: var(--surface-muted, #f3f4f6);
}

.menu-item--danger {
  color: #dc2626;
}

.menu-item--danger:hover {
  background: rgba(220, 38, 38, 0.12);
}

.thumb__id {
  margin: 0;
  opacity: 0.9;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.meta {
  padding: 0.9rem 1.1rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  flex-shrink: 0;
}

.meta__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  color: var(--muted, #4b5563);
  font-size: 0.95rem;
}

.meta__row strong {
  color: var(--text, #0f172a);
  font-size: 0.98rem;
}

.truncate {
  max-width: 180px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.empty {
  border: 1px dashed var(--border, #dfe3ec);
  border-radius: 14px;
  padding: 1.25rem;
  text-align: center;
  background: var(--surface, #ffffff);
}

.empty__title {
  margin: 0 0 0.3rem;
  font-size: 1.2rem;
  font-weight: 700;
}

.empty__body {
  margin: 0 0 0.7rem;
  color: var(--muted, #4b5563);
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  animation: fadeIn 0.15s ease;
}

.modal-dialog {
  background: var(--surface, #ffffff);
  border-radius: 16px;
  padding: 1.5rem;
  max-width: 420px;
  width: 90%;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  animation: slideUp 0.2s ease;
}

.modal-dialog h3 {
  margin: 0 0 0.75rem;
  font-size: 1.1rem;
  color: var(--text, #0f172a);
}

.modal-dialog p {
  margin: 0 0 1.1rem;
  font-size: 0.9rem;
  color: var(--muted, #6b7280);
  line-height: 1.5;
}

.modal-error {
  color: #dc2626;
  font-weight: 600;
}

.modal-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
}

.btn-cancel {
  padding: 0.6rem 1rem;
  background: var(--surface-muted, #f3f4f6);
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 8px;
  color: var(--text, #374151);
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-cancel:hover:not(:disabled) {
  background: var(--surface, #ffffff);
  border-color: var(--border-hover, #d1d5db);
}

.btn-confirm-delete {
  padding: 0.6rem 1rem;
  background: #ef4444;
  border: none;
  border-radius: 8px;
  color: #ffffff;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-confirm-delete:hover:not(:disabled) {
  background: #dc2626;
}

.skeleton-block {
  height: 60px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.05), rgba(0, 0, 0, 0.03), rgba(255, 255, 255, 0.05));
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0% {
    opacity: 0.6;
  }
  50% {
    opacity: 1;
  }
  100% {
    opacity: 0.6;
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ── Bulk Mode ── */

.ghost--active {
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: #ffffff;
  border-color: transparent;
  box-shadow: 0 6px 20px rgba(37, 99, 235, 0.25);
}

.bulk-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.7rem 1.2rem;
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 14px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.04);
  margin-bottom: 1rem;
}

.bulk-result {
  margin: -0.25rem 0 1rem;
  padding: 0.7rem 1rem;
  border-radius: 12px;
  border: 1px solid var(--border, #dfe3ec);
  background: rgba(34, 197, 94, 0.08);
  color: var(--text, #0f172a);
  font-size: 0.9rem;
  font-weight: 600;
}

.bulk-result[data-tone='warning'] {
  background: rgba(245, 158, 11, 0.12);
}

.bulk-toolbar__left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.bulk-select-all {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--text, #0f172a);
  user-select: none;
}

.bulk-select-all input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: #2563eb;
  cursor: pointer;
}

.bulk-count {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--muted, #6b7280);
}

.bulk-toolbar__right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.bulk-dropdown {
  position: relative;
}

.bulk-dropdown__trigger {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.6rem 1.1rem;
  border-radius: 10px;
  font-weight: 600;
  font-size: 0.9rem;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: #ffffff;
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.25);
}

.bulk-dropdown__trigger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
}

.bulk-dropdown__trigger:not(:disabled):hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(37, 99, 235, 0.35);
}

.bulk-dropdown__trigger svg {
  flex-shrink: 0;
}

.bulk-dropdown__menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 220px;
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 12px;
  box-shadow: 0 14px 36px rgba(0, 0, 0, 0.15);
  padding: 0.35rem;
  z-index: 100;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  animation: fadeIn 0.12s ease;
}

.bulk-dropdown__item {
  padding: 0.6rem 0.85rem;
  border: none;
  background: transparent;
  border-radius: 8px;
  text-align: left;
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text, #0f172a);
  cursor: pointer;
  transition: background 0.12s ease;
}

.bulk-dropdown__item:hover {
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.08), rgba(124, 58, 237, 0.04));
  color: #2563eb;
}

/* Card checkbox */
.bulk-check {
  position: absolute;
  top: 0.65rem;
  right: 0.65rem;
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.85);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
  backdrop-filter: blur(4px);
  cursor: pointer;
  transition: background 0.15s ease;
}

.bulk-check:hover {
  background: rgba(255, 255, 255, 1);
}

.bulk-check input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: #2563eb;
  cursor: pointer;
  pointer-events: none;
}

.project-card--selected {
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.25), 0 10px 30px rgba(0, 0, 0, 0.05);
}

@media (max-width: 900px) {
  .hero {
    flex-direction: column;
  }

  .hero__actions {
    justify-content: flex-start;
  }

  .bulk-toolbar {
    flex-direction: column;
    align-items: stretch;
    gap: 0.75rem;
  }

  .bulk-toolbar__right {
    justify-content: flex-end;
  }
}
</style>
