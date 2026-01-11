<template>
  <!-- Top hero: same width and style approach as Home hero -->
  <section class="hero">
    <router-link to="/" class="ghost btn-icon" title="Back to Projects">
      <svg class="icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
        <path d="M15 19l-7-7 7-7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      <span>Back to Projects</span>
    </router-link>
    <div class="hero__text">
      <p class="eyebrow">Settings</p>
      <h1>Application Settings</h1>
      <p class="lede">Customize theme and UI preferences. Changes apply immediately.</p>
    </div>
  </section>

  <!-- Main settings cards -->
  <section class="content">
    <!-- Theme Settings -->
    <div class="settings-card">
      <h2 class="section-title">Theme</h2>
      <div class="settings-row">
        <label class="field field--inline">
          <input type="checkbox" :checked="theme === 'dark'" @change="toggleTheme" />
          <span>Dark Theme</span>
        </label>
        <p class="muted">Current: <strong>{{ theme }}</strong></p>
      </div>
    </div>

    <!-- Column Visibility Settings -->
    <div class="settings-card">
      <h2 class="section-title">Project Card Columns</h2>
      <p class="section-description">
        Choose which metadata columns to display on project cards in the main view.
      </p>
      
      <div class="settings-group">
        <div class="settings-row">
          <label class="field field--inline">
            <input 
              type="checkbox" 
              :checked="visible_columns.created" 
              @change="handleColumnToggle('created')"
            />
            <span>Created Date</span>
          </label>
          <p class="muted">Show when each project was created</p>
        </div>

        <div class="settings-row">
          <label class="field field--inline">
            <input 
              type="checkbox" 
              :checked="visible_columns.updated" 
              @change="handleColumnToggle('updated')"
            />
            <span>Updated Date</span>
          </label>
          <p class="muted">Show when each project was last modified</p>
        </div>

        <div class="settings-row">
          <label class="field field--inline">
            <input 
              type="checkbox" 
              :checked="visible_columns.video" 
              @change="handleColumnToggle('video')"
            />
            <span>Video Path</span>
          </label>
          <p class="muted">Show the path to the project's video file</p>
        </div>
      </div>

      <div class="settings-footer">
        <button class="ghost" type="button" @click="resetSettings">
          Reset to Defaults
        </button>
      </div>
    </div>
  </section>
</template>

<script lang="ts" setup>
import { storeToRefs } from 'pinia';
import { useUserSettingsStore, type ColumnVisibility } from '../stores/userSettings';

const userSettings = useUserSettingsStore();
const { theme, visible_columns } = storeToRefs(userSettings);
const { toggleTheme, toggleColumnVisibility, resetToDefaults } = userSettings;

const handleColumnToggle = (column: keyof ColumnVisibility) => {
  toggleColumnVisibility(column);
};

const resetSettings = () => {
  if (confirm('Reset all settings to defaults?')) {
    resetToDefaults();
  }
};
</script>

<style scoped>
.hero {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1rem;
  padding: 1.25rem 1.5rem;
  border: 1px solid var(--border, #dfe3ec);
  background: var(--surface, #ffffff);
  border-radius: 18px;
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.06);
  margin-bottom: 1.25rem;
  width: 100%;
}

.hero__text { max-width: 720px; width: 100%; }
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
  cursor: pointer;
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}

.ghost:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
}

.content { 
  width: 100%; 
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.settings-card {
  width: 100%;
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 16px;
  padding: 1.25rem 1.5rem;
  background: var(--surface, #ffffff);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
}

.section-title {
  margin: 0 0 0.5rem;
  font-size: 1.3rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--text, #0f172a);
}

.section-description {
  margin: 0 0 1rem;
  color: var(--muted, #4b5563);
  font-size: 0.95rem;
  line-height: 1.5;
}

.settings-group {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-bottom: 1rem;
}

.settings-row { 
  display: flex; 
  align-items: center; 
  justify-content: space-between; 
  gap: 1rem;
  padding: 0.5rem 0;
}

.field { 
  display: flex; 
  gap: 0.6rem; 
  align-items: center;
  cursor: pointer;
}

.field--inline {
  font-weight: 600;
  font-size: 1rem;
}

.field input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: #2563eb;
}

.muted { 
  color: var(--muted, #4b5563);
  font-size: 0.9rem;
  margin: 0;
}

.settings-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border, #dfe3ec);
}

@media (max-width: 900px) {
  .hero { flex-direction: column; }
  .hero__actions { justify-content: flex-start; }
  .settings-row { flex-direction: column; align-items: flex-start; }
}
</style>
