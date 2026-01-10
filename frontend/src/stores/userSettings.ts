import { defineStore } from 'pinia';

export type Theme = 'light' | 'dark';

export interface ColumnVisibility {
  created: boolean;
  updated: boolean;
  video: boolean;
}

export interface UserSettings {
  theme: Theme;
  visible_columns: ColumnVisibility;
  column_order: string[];
}

// Cookie helper functions
const COOKIE_NAME = 'segmentflow_settings';
const COOKIE_MAX_AGE = 365 * 24 * 60 * 60; // 1 year in seconds

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : null;
}

function setCookie(name: string, value: string, maxAge: number): void {
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${maxAge}; SameSite=Lax`;
}

function loadSettingsFromCookie(): Partial<UserSettings> {
  const raw = getCookie(COOKIE_NAME);
  if (!raw) return {};
  
  try {
    return JSON.parse(raw) as Partial<UserSettings>;
  } catch (err) {
    console.warn('Failed to parse settings cookie:', err);
    return {};
  }
}

function saveSettingsToCookie(settings: UserSettings): void {
  const raw = JSON.stringify(settings);
  setCookie(COOKIE_NAME, raw, COOKIE_MAX_AGE);
}

// Default settings
const defaultSettings: UserSettings = {
  theme: 'light',
  visible_columns: {
    created: true,
    updated: true,
    video: true,
  },
  column_order: ['created', 'updated', 'video'],
};

export const useUserSettingsStore = defineStore('userSettings', {
  state: (): UserSettings => {
    const savedSettings = loadSettingsFromCookie();
    return {
      theme: savedSettings.theme ?? defaultSettings.theme,
      visible_columns: {
        ...defaultSettings.visible_columns,
        ...savedSettings.visible_columns,
      },
      column_order: savedSettings.column_order ?? defaultSettings.column_order,
    };
  },
  actions: {
    toggleTheme() {
      this.theme = this.theme === 'light' ? 'dark' : 'light';
      this.persistToCookie();
    },
    
    setTheme(theme: Theme) {
      this.theme = theme;
      this.persistToCookie();
    },
    
    setColumnVisibility(column: keyof ColumnVisibility, visible: boolean) {
      this.visible_columns[column] = visible;
      this.persistToCookie();
    },
    
    toggleColumnVisibility(column: keyof ColumnVisibility) {
      this.visible_columns[column] = !this.visible_columns[column];
      this.persistToCookie();
    },
    
    setColumnOrder(order: string[]) {
      this.column_order = order;
      this.persistToCookie();
    },
    
    resetToDefaults() {
      this.theme = defaultSettings.theme;
      this.visible_columns = { ...defaultSettings.visible_columns };
      this.column_order = [...defaultSettings.column_order];
      this.persistToCookie();
    },
    
    persistToCookie() {
      saveSettingsToCookie({
        theme: this.theme,
        visible_columns: this.visible_columns,
        column_order: this.column_order,
      });
    },
  },
});
