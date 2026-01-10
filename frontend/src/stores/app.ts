import { defineStore } from 'pinia';

export type Theme = 'light' | 'dark';

export const useAppStore = defineStore('app', {
  state: () => ({
    theme: 'light' as Theme,
    counter: 0,
  }),
  actions: {
    toggleTheme() {
      this.theme = this.theme === 'light' ? 'dark' : 'light';
    },
    increment() {
      this.counter += 1;
    },
  },
});
