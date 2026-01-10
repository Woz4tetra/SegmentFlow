<template>
  <section>
    <h1>Settings</h1>
    <p>Demonstrates router + Pinia theme toggle.</p>

    <div class="card">
      <label>
        <input type="checkbox" :checked="theme === 'dark'" @change="toggleTheme" />
        Dark Theme
      </label>
      <p>Current theme: <strong>{{ theme }}</strong></p>
    </div>
  </section>
</template>

<script lang="ts" setup>
import { storeToRefs } from 'pinia';
import { useAppStore } from '../stores/app';

const app = useAppStore();
const { theme } = storeToRefs(app);
const { toggleTheme } = app;
</script>

<style scoped>
.card {
  margin-top: 1rem;
  padding: 1rem;
  border-radius: 8px;
  background: rgba(127, 127, 127, 0.08);
}
</style>
