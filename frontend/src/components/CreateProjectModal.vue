<template>
  <div v-if="open" class="overlay" @click.self="onClose">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="create-title">
      <header class="modal__header">
        <h2 id="create-title">Create Project</h2>
      </header>
      <form class="modal__body" @submit.prevent="submit">
        <label class="field">
          <span>Name</span>
          <input
            ref="nameInput"
            v-model.trim="name"
            type="text"
            placeholder="e.g., My Video Annotation"
            :disabled="submitting"
            required
            minlength="1"
          />
        </label>

        <p v-if="error" class="error" role="alert">{{ error }}</p>
      </form>
      <footer class="modal__footer">
        <button type="button" class="ghost" @click="onClose" :disabled="submitting">Cancel</button>
        <button type="button" class="primary" @click="submit" :disabled="disabled">
          {{ submitting ? 'Creating...' : 'Create Project' }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { nextTick, ref, watch, computed } from 'vue';

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'submit', payload: { name: string; active: boolean }): void;
}>();

const name = ref('');
const active = ref(true);
const error = ref('');
const submitting = ref(false);
const nameInput = ref<HTMLInputElement | null>(null);

const disabled = computed(() => submitting.value || name.value.length < 1);

watch(
  () => props.open,
  async (isOpen) => {
    if (isOpen) {
      error.value = '';
      submitting.value = false;
      await nextTick();
      nameInput.value?.focus();
    }
  },
);

function onClose() {
  if (submitting.value) return;
  emit('close');
}

async function submit() {
  if (disabled.value) return;
  error.value = '';
  submitting.value = true;
  try {
    emit('submit', { name: name.value, active: true });
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to create project';
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 17, 26, 0.45);
  display: grid;
  place-items: center;
  z-index: 50;
}
.modal {
  width: min(640px, calc(100% - 2rem));
  border-radius: 16px;
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #dfe3ec);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.2);
}
.modal__header {
  padding: 1rem 1.25rem 0.5rem;
}
.modal__body {
  padding: 0 1.25rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 0 1.25rem 1.25rem;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.field span {
  font-weight: 600;
}
.field input[type='text'] {
  padding: 0.6rem 0.7rem;
  border-radius: 10px;
  border: 1px solid var(--border, #dfe3ec);
  background: var(--surface-muted, #eef2f7);
  color: var(--text, #0f172a);
}
.field--inline {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}
.error {
  color: #b91c1c;
  margin: 0.5rem 0 0;
}
.primary,
.ghost {
  padding: 0.55rem 0.9rem;
  border-radius: 12px;
  font-weight: 600;
  border: 1px solid transparent;
  cursor: pointer;
}
.primary {
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: #ffffff;
  border-color: rgba(124, 58, 237, 0.35);
}
.ghost {
  background: var(--surface, #ffffff);
  border-color: var(--border, #dfe3ec);
  color: var(--text, #0f172a);
}
</style>
