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
          <span v-else class="stage-number">{{ index }}</span>
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
  { id: 'validation', name: 'Validation', route: 'Validation' },
  { id: 'export', name: 'Export', route: 'Home' },
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
  width: 100%;
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.04), rgba(99, 102, 241, 0.02));
  border-bottom: 1px solid #dfe3ec;
  margin-bottom: 0;
  padding: 0.875rem 1.25rem;
}

.stage-track {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  max-width: 1400px;
  margin: 0 auto;
  position: relative;
  padding: 0 1.5rem;
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
}

.stage-item.locked .stage-circle {
  opacity: 1.0;
}

.stage-item.locked .stage-label {
  opacity: 1.0;
}

.stage-item:not(.locked):hover .stage-circle {
  transform: scale(1.1);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
}

.stage-connector {
  position: absolute;
  top: 20px;
  right: 50%;
  width: 100%;
  height: 2px;
  background: #dfe3ec;
  z-index: 0;
}

.stage-item.completed .stage-connector,
.stage-item.active .stage-connector {
  background: linear-gradient(90deg, #2563eb, #7c3aed);
}

.stage-circle {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: #ffffff;
  border: 2px solid #dfe3ec;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 1;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  color: #374151;
}

.stage-item.active .stage-circle {
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  border-color: transparent;
  color: white;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.3);
}

.stage-item.completed .stage-circle {
  background: linear-gradient(135deg, #22c55e, #16a34a);
  border-color: transparent;
  color: white;
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.2);
}

.stage-item.locked .stage-circle {
  background: #9ca3af;
  border-color: #9ca3af;
  color: white;
}

.stage-item.locked .stage-label {
  color: #6b7280;
}

@media (prefers-color-scheme: dark) {
  .stage-item.locked .stage-circle {
    background: #9ca3af;
    border-color: #9ca3af;
    color: white;
  }
  
  .stage-item.locked .stage-label {
    color: #6b7280;
  }
}
</style>
