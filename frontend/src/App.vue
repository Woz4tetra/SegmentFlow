<template>
  <div :class="['app', themeClass]">
    <header class="container container--nav">
      <NavBar />
    </header>
    <main class="container">
      <router-view />
    </main>
  </div>
</template>

<script lang="ts" setup>
import { computed } from 'vue';
import NavBar from './components/NavBar.vue';
import { storeToRefs } from 'pinia';
import { useAppStore } from './stores/app';

const app = useAppStore();
const { theme } = storeToRefs(app);
const themeClass = computed(() => (theme.value === 'dark' ? 'theme-dark' : 'theme-light'));
</script>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg, #f6f7fb);
  color: var(--text, #0f172a);
}
.container {
  max-width: 1180px;
  width: 100%;
  margin: 1.25rem auto;
  padding: 0 1.25rem;
  display: grid;
  place-items: start center;
}

.container--nav {
  margin-bottom: 0.75rem;
}
.theme-light {
  --bg: #f5f7fb;
  --surface: #ffffff;
  --surface-muted: #eef2f7;
  --border: #dfe3ec;
  --text: #0f172a;
  --muted: #4b5563;
  --pill: #e2e8f0;
}
.theme-dark {
  --bg: #0d111a;
  --surface: #101524;
  --surface-muted: #151b2b;
  --border: #1e2535;
  --text: #e8edf5;
  --muted: #9aa3b5;
  --pill: #1f2937;
}
</style>
