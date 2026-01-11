<template>
  <div
    class="file-upload"
    :class="{
      'file-upload--dragging': isDragging,
      'file-upload--uploading': isUploading,
      'file-upload--disabled': disabled
    }"
    @dragenter.prevent="handleDragEnter"
    @dragover.prevent="handleDragOver"
    @dragleave.prevent="handleDragLeave"
    @drop.prevent="handleDrop"
  >
    <input
      ref="fileInputRef"
      type="file"
      :accept="accept"
      :disabled="disabled"
      class="file-upload__input"
      @change="handleFileSelect"
    />

    <div class="file-upload__content">
      <template v-if="!isUploading">
        <!-- Upload icon -->
        <img
          src="/cloud_upload_256dp_000000_FILL0_wght400_GRAD0_opsz48.svg"
          alt="Upload icon"
          class="file-upload__icon"
          width="64"
          height="64"
        />

        <div class="file-upload__text">
          <p class="file-upload__title">
            {{ isDragging ? 'Drop video file here' : 'Drag and drop video file' }}
          </p>
          <p class="file-upload__subtitle">or</p>
          <button
            type="button"
            class="file-upload__button"
            :disabled="disabled"
            @click="triggerFileInput"
          >
            Browse Files
          </button>
          <p class="file-upload__hint">{{ hint }}</p>
        </div>
      </template>

      <template v-else>
        <!-- Upload progress -->
        <div class="file-upload__progress-container">
          <div class="file-upload__progress-info">
            <p class="file-upload__progress-title">{{ uploadingFileName }}</p>
            <p class="file-upload__progress-percentage">{{ uploadProgress }}%</p>
          </div>
          <div class="file-upload__progress-bar">
            <div
              class="file-upload__progress-fill"
              :style="{ width: `${uploadProgress}%` }"
            ></div>
          </div>
          <p class="file-upload__progress-status">{{ progressStatus }}</p>
        </div>
      </template>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed } from 'vue';

interface Props {
  accept?: string;
  hint?: string;
  disabled?: boolean;
  uploadProgress?: number;
  isUploading?: boolean;
  uploadingFileName?: string;
}

interface Emits {
  (e: 'file-selected', file: File): void;
}

const props = withDefaults(defineProps<Props>(), {
  accept: 'video/*',
  hint: 'Supported formats: MP4, AVI, MOV',
  disabled: false,
  uploadProgress: 0,
  isUploading: false,
  uploadingFileName: '',
});

const emit = defineEmits<Emits>();

const fileInputRef = ref<HTMLInputElement | null>(null);
const isDragging = ref(false);
const dragCounter = ref(0); // Track nested drag events

const progressStatus = computed(() => {
  if (props.uploadProgress < 25) return 'Initializing upload...';
  if (props.uploadProgress < 100) return 'Uploading video...';
  return 'Finalizing...';
});

const handleDragEnter = (e: DragEvent) => {
  if (props.disabled || props.isUploading) return;
  dragCounter.value++;
  if (e.dataTransfer?.types.includes('Files')) {
    isDragging.value = true;
  }
};

const handleDragOver = (e: DragEvent) => {
  if (props.disabled || props.isUploading) return;
  if (e.dataTransfer) {
    e.dataTransfer.dropEffect = 'copy';
  }
};

const handleDragLeave = () => {
  if (props.disabled || props.isUploading) return;
  dragCounter.value--;
  if (dragCounter.value === 0) {
    isDragging.value = false;
  }
};

const handleDrop = (e: DragEvent) => {
  if (props.disabled || props.isUploading) return;
  
  dragCounter.value = 0;
  isDragging.value = false;

  const files = e.dataTransfer?.files;
  if (files && files.length > 0) {
    const file = files[0];
    emit('file-selected', file);
  }
};

const handleFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  
  if (file) {
    emit('file-selected', file);
  }
  
  // Reset input value so same file can be selected again
  if (fileInputRef.value) {
    fileInputRef.value.value = '';
  }
};

const triggerFileInput = () => {
  if (!props.disabled && !props.isUploading && fileInputRef.value) {
    fileInputRef.value.click();
  }
};
</script>

<style scoped>
.file-upload {
  width: 100%;
  min-height: 420px;
  border: 2px dashed var(--border, #dfe3ec);
  border-radius: 16px;
  padding: 3rem;
  background: var(--surface, #ffffff);
  transition: all var(--transition-duration, 0.2s) ease;
  cursor: pointer;
  position: relative;
}

.file-upload:hover:not(.file-upload--disabled):not(.file-upload--uploading) {
  border-color: #7c3aed;
  background: var(--surface-muted, #fafbfd);
}

.file-upload--dragging {
  border-color: #2563eb;
  background: rgba(37, 99, 235, 0.05);
  transform: scale(1.01);
}

.file-upload--uploading {
  border-style: solid;
  cursor: default;
}

.file-upload--disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.file-upload__input {
  display: none;
}

.file-upload__content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1.25rem;
  min-height: 340px;
}

.file-upload__icon {
  /* Recolor black SVG to match text color using CSS filter */
  opacity: 0.6;
  transition: opacity var(--transition-duration, 0.2s) ease, transform var(--transition-duration, 0.2s) ease, filter var(--transition-duration, 0.2s) ease;
}

.file-upload--dragging .file-upload__icon {
  opacity: 1;
  transform: scale(1.1);
}


.file-upload__text {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.file-upload__title {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text, #0f172a);
  margin: 0;
}

.file-upload__subtitle {
  font-size: 0.9rem;
  color: var(--muted, #4b5563);
  margin: 0;
}

.file-upload__button {
  padding: 0.65rem 1.4rem;
  border-radius: 10px;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: #ffffff;
  font-weight: 600;
  border: 1px solid rgba(124, 58, 237, 0.35);
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.25);
  transition: transform var(--transition-duration, 0.2s) ease, box-shadow var(--transition-duration, 0.2s) ease;
  font-size: 0.95rem;
}

.file-upload__button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 12px 30px rgba(37, 99, 235, 0.32);
}

.file-upload__button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.file-upload__hint {
  font-size: 0.85rem;
  color: var(--muted, #6b7280);
  margin: 0.25rem 0 0;
}

/* Progress styles */
.file-upload__progress-container {
  width: 100%;
  max-width: 500px;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.file-upload__progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.file-upload__progress-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text, #0f172a);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.file-upload__progress-percentage {
  font-size: 1.1rem;
  font-weight: 700;
  color: #2563eb;
  margin: 0;
  flex-shrink: 0;
}

.file-upload__progress-bar {
  width: 100%;
  height: 12px;
  background: var(--surface-muted, #eef2f7);
  border-radius: 8px;
  overflow: hidden;
  position: relative;
}

.file-upload__progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #2563eb, #7c3aed);
  border-radius: 8px;
  transition: width var(--transition-duration, 0.3s) ease;
  position: relative;
}

.file-upload__progress-fill::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.3),
    transparent
  );
  animation: shimmer 2s infinite;
}

@keyframes shimmer {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

.file-upload__progress-status {
  font-size: 0.9rem;
  color: var(--muted, #4b5563);
  margin: 0;
  text-align: center;
}
</style>

<style>
/* Unscoped style for dark theme icon inversion */
.theme-dark .file-upload__icon {
  filter: invert(1);
}
</style>
