import { defineStore } from 'pinia';
import { useUserSettingsStore } from './userSettings';

export type Theme = 'light' | 'dark';

export const useAppStore = defineStore('app', {
  state: () => ({
    // Theme is now managed by userSettings store
  }),
  getters: {
    theme(): Theme {
      const userSettings = useUserSettingsStore();
      return userSettings.theme;
    },
  },
  actions: {
    toggleTheme() {
      const userSettings = useUserSettingsStore();
      userSettings.toggleTheme();
    },
  },
});
