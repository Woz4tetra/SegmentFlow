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
        <span class="pill pill--muted">Auto-save & real-time</span>
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
        :data-available="isStageAvailable(project.stage)"
        role="button"
        tabindex="0"
        :title="isStageAvailable(project.stage) ? 'Open editor' : 'Editor coming soon for this stage'"
        @click="goToStage(project)"
        @keydown.enter="goToStage(project)"
      >
        <div class="thumb" :style="gradientStyle(project)">
          <div class="thumb__top">
            <span
              class="stage"
              :data-tone="toneForStage(project.stage)"
            >
              {{ labelForStage(project.stage) }}
            </span>
            <span class="status" :data-active="project.active">
              {{ project.active ? 'Active' : 'Archived' }}
            </span>
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
            <strong class="truncate">{{ project.video_path }}</strong>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<script lang="ts" setup>
import { computed, onMounted, ref } from 'vue';
import { storeToRefs } from 'pinia';
import type { Project, ProjectStage } from '../stores/projects';
import { useProjectsStore } from '../stores/projects';
import { useUserSettingsStore } from '../stores/userSettings';
import { useRouter } from 'vue-router';

const projectsStore = useProjectsStore();
const { projects, total, loading, error } = storeToRefs(projectsStore);
const { fetchProjects } = projectsStore;

const userSettingsStore = useUserSettingsStore();
const { visible_columns } = storeToRefs(userSettingsStore);

const router = useRouter();

const stageMeta: Record<ProjectStage, { label: string; tone: 'info' | 'warn' | 'success' | 'accent' }> = {
  upload: { label: 'Stage 1 / Upload', tone: 'accent' },
  trim: { label: 'Stage 2 / Trim', tone: 'info' },
  manual_labeling: { label: 'Stage 3 / Manual Labeling', tone: 'accent' },
  propagation: { label: 'Stage 4 / Propagation', tone: 'info' },
  validation: { label: 'Stage 5 / Validation', tone: 'warn' },
  export: { label: 'Stage 6 / Export', tone: 'success' },
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

const labelForStage = (stage: ProjectStage): string => stageMeta[stage]?.label ?? 'Unknown stage';
const toneForStage = (stage: ProjectStage): string => stageMeta[stage]?.tone ?? 'info';

const isStageAvailable = (stage: ProjectStage): boolean => stage === 'upload';

const routeForProject = (project: Project) => {
  if (project.stage === 'upload' && project.id) {
    return { name: 'Upload', params: { id: project.id } };
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

onMounted(() => {
  fetchProjects();
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
  transition: transform 0.12s ease, box-shadow 0.12s ease, opacity 0.12s ease;
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
  gap: 1rem;
  grid-template-columns: 1fr;
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
  min-height: 150px;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.thumb__top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stage {
  padding: 0.3rem 0.6rem;
  border-radius: 12px;
  font-weight: 700;
  font-size: 0.85rem;
  background: rgba(0, 0, 0, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.4);
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

@media (max-width: 900px) {
  .hero {
    flex-direction: column;
  }

  .hero__actions {
    justify-content: flex-start;
  }
}
</style>
