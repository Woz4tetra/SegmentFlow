<template>
  <section class="upload">
    <h1>Stage 1 / Upload</h1>
    <p>Project ID: <strong>{{ id }}</strong></p>
    <p>This is a placeholder Upload page. You can add drag-and-drop and progress in VIDEO-002 later.</p>
    <div class="actions">
      <router-link class="ghost" to="/">Back to Projects</router-link>
    </div>
  </section>
</template>

<script lang="ts" setup>
import { useRoute } from 'vue-router';
const route = useRoute();
const id = route.params.id as string;
</script>

<style scoped>
.upload { 
  border: 1px solid var(--border, #dfe3ec);
  border-radius: 16px;
  padding: 1rem 1.25rem;
  background: var(--surface, #ffffff);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
}
.actions { margin-top: 1rem; }
.ghost {
  display: inline-block;
  padding: 0.5rem 0.8rem;
  border-radius: 10px;
  border: 1px solid var(--border, #dfe3ec);
  background: var(--surface, #ffffff);
  color: var(--text, #0f172a);
}
</style>
