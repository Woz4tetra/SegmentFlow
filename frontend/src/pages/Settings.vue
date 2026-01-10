<template>
  <!-- Top hero: same width and style approach as Home hero -->
  <section class="hero">
    <div class="hero__text">
      <p class="eyebrow">Settings</p>
      <h1>Application Settings</h1>
      <p class="lede">Customize theme and UI preferences. Changes apply immediately.</p>
    </div>
    <div class="hero__actions">
      <router-link to="/" class="ghost btn-icon" title="Back to Projects">
        <svg class="icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
          <path d="M15 19l-7-7 7-7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <span>Back to Projects</span>
      </router-link>
    </div>
  </section>

  <!-- Main settings card: full-width like Home hero card -->
  <section class="content">
    <div class="settings-card">
      <div class="settings-row">
        <label class="field field--inline">
          <input type="checkbox" :checked="theme === 'dark'" @change="toggleTheme" />
          <span>Dark Theme</span>
        </label>
        <p class="muted">Current: <strong>{{ theme }}</strong></p>
      </div>
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
.hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.5rem;
  padding: 1.25rem 1.5rem;
  border: 1px solid var(--border, #dfe3ec);
  background: var(--surface, #ffffff);
  border-radius: 18px;
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.06);
  margin-bottom: 1.25rem;
  width: 100%;
}

.hero__text { max-width: 720px; }
.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 700;
  font-size: 0.8rem;
  color: var(--muted, #5b6474);
  margin: 0 0 0.35rem;
}
h1 { margin: 0 0 0.25rem; font-size: 2rem; letter-spacing: -0.02em; }
.lede { margin: 0 0 0.75rem; color: var(--muted, #4b5563); line-height: 1.6; }
.hero__actions { display: flex; gap: 0.75rem; flex-wrap: wrap; justify-content: flex-end; }

.btn-icon { display: inline-flex; align-items: center; gap: 0.5rem; }
.ghost {
  background: var(--surface, #ffffff);
  border: 1px solid var(--border, #dfe3ec);
  color: var(--text, #0f172a);
  padding: 0.55rem 0.9rem;
  border-radius: 12px;
  font-weight: 600;
  text-decoration: none;
}

.content { width: 100%; }
.settings-card {
  width: 100%;
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 16px;
  padding: 1rem 1.25rem;
  background: var(--surface, #ffffff);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
}
.settings-row { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.field { display: flex; gap: 0.5rem; align-items: center; }
.muted { color: var(--muted, #4b5563); }

@media (max-width: 900px) {
  .hero { flex-direction: column; }
  .hero__actions { justify-content: flex-start; }
  .settings-row { flex-direction: column; align-items: flex-start; }
}
</style>
