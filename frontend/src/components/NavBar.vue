<template>
  <nav class="navbar">
    <div class="brand">
      <router-link to="/" class="brand-link">
        <img src="/icons/home.svg" alt="Home" class="icon" />
        <span class="brand-text">SegmentFlow</span>
      </router-link>
    </div>
    <div class="links">
      <router-link to="/" class="nav-btn" title="Home (H)">
        <img src="/home_256dp_000000_FILL0_wght400_GRAD0_opsz48.svg" alt="Home" class="icon" />
        <span>Home</span>
      </router-link>
      <router-link to="/labels" class="nav-btn" title="Label Editor (L)">
        <img src="/label_256dp_000000_FILL0_wght400_GRAD0_opsz48.svg" alt="Labels" class="icon" />
        <span>Labels</span>
      </router-link>
      <router-link to="/settings" class="nav-btn" title="Settings (S)">
        <img src="/settings_256dp_000000_FILL0_wght400_GRAD0_opsz48.svg" alt="Settings" class="icon" />
        <span>Settings</span>
      </router-link>
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
.brand-link { display: flex; align-items: center; gap: 0.5rem; }
.brand-text { font-weight: 700; }
.links {
  display: flex;
  align-items: center;
  gap: 1rem;
}
.links a.nav-btn {
  text-decoration: none;
  color: inherit;
  transition: color var(--transition-duration, 0.2s) ease, opacity var(--transition-duration, 0.2s) ease;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.6rem;
  border-radius: 8px;
}
.links a.nav-btn:hover {
  opacity: 0.7;
  background: var(--surface-muted, #eef2f7);
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
.icon { width: 20px; height: 20px; display: inline-block; }
</style>
