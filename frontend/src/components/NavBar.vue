<template>
  <nav class="navbar">
    <div class="brand">
      <router-link to="/">SegmentFlow</router-link>
    </div>
    <div class="links">
      <router-link to="/">Home</router-link>
      <router-link to="/settings">Settings</router-link>
      <button class="theme" @click="toggleTheme" :title="`Toggle Theme (current: ${theme})`">
        {{ theme === 'dark' ? '🌙' : '☀️' }}
      </button>
    </div>
  </nav>
</template>

<script lang="ts" setup>
import { storeToRefs } from 'pinia';
import { useAppStore } from '../stores/app';

const app = useAppStore();
const { theme } = storeToRefs(app);
const { toggleTheme } = app;
</script>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.9rem 1.1rem;
  border: 1px solid var(--border, #dfe3ec);
  background: var(--surface, #ffffff);
  border-radius: 14px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.04);
  width: 100%;
  transition: background var(--transition-duration, 0.2s) ease, border-color var(--transition-duration, 0.2s) ease, box-shadow var(--transition-duration, 0.2s) ease;
}
.brand a {
  font-weight: 700;
  text-decoration: none;
  color: inherit;
  transition: color var(--transition-duration, 0.2s) ease;
}
.links {
  display: flex;
  align-items: center;
  gap: 1rem;
}
.links a {
  text-decoration: none;
  color: inherit;
  transition: color var(--transition-duration, 0.2s) ease, opacity var(--transition-duration, 0.2s) ease;
}
.links a:hover {
  opacity: 0.7;
}
.theme {
  border: 1px solid var(--border, #dfe3ec);
  background: var(--surface-muted, #eef2f7);
  border-radius: 6px;
  padding: 0.25rem 0.5rem;
  cursor: pointer;
  transition: background var(--transition-duration, 0.2s) ease, border-color var(--transition-duration, 0.2s) ease, transform var(--transition-duration, 0.2s) ease;
}
.theme:hover {
  transform: scale(1.05);
}
</style>
