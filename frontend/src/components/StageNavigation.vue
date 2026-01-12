<template>
  <div class="stage-navigation">
    <div class="stage-track">
      <div
        v-for="(stage, index) in stages"
        :key="stage.id"
        class="stage-item"
        :class="{
          active: stage.id === currentStage,
          completed: isStageCompleted(stage.id),
          locked: !canAccessStage(stage.id),
        }"
        @click="navigateToStage(stage.id)"
        :title="getStageTooltip(stage)"
      >
        <div class="stage-connector" v-if="index > 0"></div>
        <div class="stage-circle">
          <svg v-if="isStageCompleted(stage.id)" class="stage-icon" viewBox="0 0 24 24" width="16" height="16">
            <path d="M5 12l5 5L20 7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span v-else class="stage-number">{{ index + 1 }}</span>
        </div>
        <div class="stage-label">{{ stage.name }}</div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { computed } from 'vue';
import { useRouter } from 'vue-router';

interface Stage {
  id: string;
  name: string;
  route: string;
}

interface Project {
  id: string;
  stage: string;
  upload_visited: boolean;
  trim_visited: boolean;
  manual_labeling_visited: boolean;
  propagation_visited: boolean;
  validation_visited: boolean;
  export_visited: boolean;
}

const props = defineProps<{
  project: Project;
}>();

const router = useRouter();

const stages: Stage[] = [
  { id: 'upload', name: 'Upload', route: 'Upload' },
  { id: 'trim', name: 'Trim', route: 'Trim' },
  { id: 'manual_labeling', name: 'Manual Label', route: 'ManualLabeling' },
  { id: 'propagation', name: 'Propagate', route: 'Propagation' },
];

const currentStage = computed(() => props.project.stage);

const stageOrder = ['upload', 'trim', 'manual_labeling', 'propagation', 'validation', 'export'];

function isStageCompleted(stageId: string): boolean {
  const currentIndex = stageOrder.indexOf(currentStage.value);
  const stageIndex = stageOrder.indexOf(stageId);
  return stageIndex < currentIndex;
}

function canAccessStage(stageId: string): boolean {
  // Always allow access to upload
  if (stageId === 'upload') return true;

  // Map stage ID to visited field
  const visitedMap: Record<string, keyof Project> = {
    upload: 'upload_visited',
    trim: 'trim_visited',
    manual_labeling: 'manual_labeling_visited',
    propagation: 'propagation_visited',
    validation: 'validation_visited',
    export: 'export_visited',
  };

  // Get the index of the stage we want to access
  const targetIndex = stageOrder.indexOf(stageId);
  
  // Check if all previous stages have been visited
  for (let i = 0; i < targetIndex; i++) {
    const prevStageId = stageOrder[i];
    const visitedField = visitedMap[prevStageId];
    if (!props.project[visitedField]) {
      return false;
    }
  }
  
  return true;
}

function getStageTooltip(stage: Stage): string {
  if (!canAccessStage(stage.id)) {
    return 'Complete previous stages to unlock';
  }
  if (stage.id === currentStage.value) {
    return `Current stage: ${stage.name}`;
  }
  if (isStageCompleted(stage.id)) {
    return `${stage.name} (Completed)`;
  }
  return `Go to ${stage.name}`;
}

function navigateToStage(stageId: string): void {
  if (!canAccessStage(stageId)) {
    return;
  }
  
  const stage = stages.find(s => s.id === stageId);
  if (stage) {
    router.push({ name: stage.route, params: { id: props.project.id } });
  }
}
</script>

<style scoped>
.stage-navigation {
  padding: 1.5rem 2rem;
  background: var(--color-bg-secondary);
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 2rem;
}

.stage-track {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 800px;
  margin: 0 auto;
  position: relative;
}

.stage-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  cursor: pointer;
  transition: all 0.2s ease;
}

.stage-item.locked {
  cursor: not-allowed;
  opacity: 0.4;
}

.stage-item:not(.locked):hover .stage-circle {
  transform: scale(1.1);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.stage-connector {
  position: absolute;
  top: 20px;
  right: 50%;
  width: 100%;
  height: 2px;
  background: var(--color-border);
  z-index: 0;
}

.stage-item.completed .stage-connector,
.stage-item.active .stage-connector {
  background: var(--color-primary);
}

.stage-circle {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--color-bg);
  border: 2px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 1;
  transition: all 0.2s ease;
}

.stage-item.active .stage-circle {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: white;
  box-shadow: 0 2px 8px rgba(var(--color-primary-rgb), 0.4);
}

.stage-item.completed .stage-circle {
  background: var(--color-success);
  border-color: var(--color-success);
  color: white;
}

.stage-item.locked .stage-circle {
  background: var(--color-bg-tertiary);
  border-color: var(--color-border);
  color: var(--color-text-secondary);
}

.stage-number {
  font-weight: 600;
  font-size: 0.875rem;
}

.stage-icon {
  color: currentColor;
}

.stage-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--color-text);
  text-align: center;
  white-space: nowrap;
}

.stage-item.active .stage-label {
  color: var(--color-primary);
  font-weight: 600;
}

.stage-item.locked .stage-label {
  color: var(--color-text-secondary);
}

/* Dark theme support */
:root {
  --color-bg: #ffffff;
  --color-bg-secondary: #f8f9fa;
  --color-bg-tertiary: #e9ecef;
  --color-text: #212529;
  --color-text-secondary: #6c757d;
  --color-border: #dee2e6;
  --color-primary: #0d6efd;
  --color-primary-rgb: 13, 110, 253;
  --color-success: #198754;
}

[data-theme="dark"] {
  --color-bg: #1a1a1a;
  --color-bg-secondary: #2d2d2d;
  --color-bg-tertiary: #3a3a3a;
  --color-text: #e9ecef;
  --color-text-secondary: #adb5bd;
  --color-border: #495057;
}
</style>
