<template>
  <div :class="['app', themeClass]">
    <NavBar />
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
}
.container {
  max-width: 980px;
  margin: 1rem auto;
  padding: 0 1rem;
  flex: 1;
}
.theme-light {
  background: #f6f7fb;
  color: #1a1a1a;
}
.theme-dark {
  background: #0f1115;
  color: #e6e6e6;
}
</style>
