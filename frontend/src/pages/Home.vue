<template>
  <section>
    <h1>SegmentFlow</h1>
    <p>Vue 3 + Vite is running. Routing and Pinia are wired.</p>

    <div class="card">
      <h3>Pinia Counter</h3>
      <p>Counter: <strong>{{ counter }}</strong></p>
      <button @click="increment">Increment</button>
    </div>

    <p>
      Try navigating to <router-link to="/settings">Settings</router-link> to test routing.
    </p>
  </section>
</template>

<script lang="ts" setup>
import { storeToRefs } from 'pinia';
import { useAppStore } from '../stores/app';

const app = useAppStore();
const { counter } = storeToRefs(app);
const { increment } = app;
</script>

<style scoped>
.card {
  margin-top: 1rem;
  padding: 1rem;
  border-radius: 8px;
  background: rgba(127, 127, 127, 0.08);
}
button {
  margin-top: 0.5rem;
}
</style>
