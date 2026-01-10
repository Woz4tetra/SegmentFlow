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
  padding: 0.75rem 1rem;
  border-bottom: 1px solid rgba(127,127,127,0.25);
}
.brand a {
  font-weight: 700;
  text-decoration: none;
  color: inherit;
}
.links {
  display: flex;
  align-items: center;
  gap: 1rem;
}
.links a {
  text-decoration: none;
  color: inherit;
}
.theme {
  border: 1px solid rgba(127,127,127,0.4);
  background: transparent;
  border-radius: 6px;
  padding: 0.25rem 0.5rem;
  cursor: pointer;
}
</style>
