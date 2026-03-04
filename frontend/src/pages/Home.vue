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
      <button class="ghost" type="button" :disabled="loading" @click="handleRefresh">
        {{ loading ? 'Refreshing...' : 'Refresh' }}
      </button>
      <button class="primary" type="button" @click="handleCreateProject">
        + New Project
      </button>
    </div>
  </section>

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
        class="project-card"
        :data-available="isStageAvailable(effectiveStage(project))"
        role="button"
        tabindex="0"
        :title="isStageAvailable(effectiveStage(project)) ? 'Open editor' : 'Editor coming soon for this stage'"
        @click="goToStage(project)"
        @keydown.enter="goToStage(project)"
      >
        <div class="thumb" :style="project.video_path ? {} : gradientStyle(project)">
          <img
            v-if="project.video_path"
            :src="getThumbnailUrl(project.id)"
            alt=""
            class="thumb__img"
            @error="onThumbnailError"
          />
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
import { API_BASE_URL } from '../lib/api';

const projectsStore = useProjectsStore();
const { projects, total, loading, error } = storeToRefs(projectsStore);
const { fetchProjects, deleteProject } = projectsStore;

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

const handleGlobalClick = () => {
  if (openMenuId.value) {
    closeMenu();
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

@media (max-width: 900px) {
  .hero {
    flex-direction: column;
  }

  .hero__actions {
    justify-content: flex-start;
  }
}
</style>
