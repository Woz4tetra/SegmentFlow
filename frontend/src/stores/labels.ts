import axios from 'axios';
import { defineStore } from 'pinia';

export interface Label {
  id: string;
  name: string;
  color_hex: string; // #RRGGBB
  thumbnail_path?: string | null;
  created_at: string;
  updated_at: string;
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1',
  timeout: 8000,
});

export type NamedColor = {
  name: string;
  hex: string;
};

// A reasonably large accessible named color palette (subset)
export const namedColors: NamedColor[] = [
  { name: 'red', hex: '#EF4444' },
  { name: 'orange', hex: '#F97316' },
  { name: 'amber', hex: '#F59E0B' },
  { name: 'yellow', hex: '#EAB308' },
  { name: 'lime', hex: '#84CC16' },
  { name: 'green', hex: '#22C55E' },
  { name: 'emerald', hex: '#10B981' },
  { name: 'teal', hex: '#14B8A6' },
  { name: 'cyan', hex: '#06B6D4' },
  { name: 'sky', hex: '#0EA5E9' },
  { name: 'blue', hex: '#3B82F6' },
  { name: 'indigo', hex: '#6366F1' },
  { name: 'violet', hex: '#8B5CF6' },
  { name: 'purple', hex: '#A855F7' },
  { name: 'fuchsia', hex: '#D946EF' },
  { name: 'pink', hex: '#EC4899' },
  { name: 'rose', hex: '#F43F5E' },
  { name: 'slate', hex: '#64748B' },
  { name: 'gray', hex: '#6B7280' },
  { name: 'neutral', hex: '#737373' },
];

function randomPaletteHex(): string {
  const idx = Math.floor(Math.random() * namedColors.length);
  return namedColors[idx].hex;
}

function clamp(v: number, min = 0, max = 255): number { return Math.max(min, Math.min(max, v)); }
function componentToHex(c: number): string { const h = clamp(c).toString(16).padStart(2, '0'); return h.toUpperCase(); }

export function parseColorInput(input: string): string | null {
  if (!input) return null;
  const v = input.trim();
  // Hex #RRGGBB
  if (/^#([0-9a-fA-F]{6})$/.test(v)) return v.toUpperCase();
  // rgb(r,g,b)
  const rgbMatch = v.match(/^rgb\s*\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$/i);
  if (rgbMatch) {
    const r = Number(rgbMatch[1]);
    const g = Number(rgbMatch[2]);
    const b = Number(rgbMatch[3]);
    return `#${componentToHex(r)}${componentToHex(g)}${componentToHex(b)}`;
  }
  // Named color
  const named = namedColors.find((c) => c.name.toLowerCase() === v.toLowerCase());
  if (named) return named.hex.toUpperCase();
  return null;
}

export const useLabelsStore = defineStore('labels', {
  state: () => ({
    labels: [] as Label[],
    loading: false,
    error: '' as string,
  }),
  actions: {
    async listLabels(): Promise<Label[]> {
      this.loading = true; this.error = '';
      try {
        const { data } = await api.get<Label[]>(`/labels`);
        this.labels = data ?? [];
        return this.labels;
      } catch (err) {
        const msg = axios.isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : err instanceof Error ? err.message : 'Failed to load labels';
        this.error = msg; return [];
      } finally { this.loading = false; }
    },
    async createLabel(name: string, colorHex?: string): Promise<Label | null> {
      try {
        const color = (colorHex && parseColorInput(colorHex)) || randomPaletteHex();
        const { data } = await api.post<Label>(`/labels`, { name, color_hex: color });
        this.labels = [...this.labels, data];
        return data;
      } catch (err) {
        const msg = axios.isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : err instanceof Error ? err.message : 'Failed to create label';
        this.error = msg; return null;
      }
    },
    async updateLabel(labelId: string, payload: Partial<{ name: string; color_hex: string; thumbnail_path: string | null }>): Promise<Label | null> {
      try {
        const upd = { ...payload } as any;
        if (upd.color_hex) {
          const parsed = parseColorInput(upd.color_hex);
          if (!parsed) throw new Error('Invalid color format');
          upd.color_hex = parsed;
        }
        const { data } = await api.patch<Label>(`/labels/${labelId}`, upd);
        this.labels = this.labels.map((l) => (l.id === labelId ? data : l));
        return data;
      } catch (err) {
        const msg = axios.isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : err instanceof Error ? err.message : 'Failed to update label';
        this.error = msg; return null;
      }
    },
    async uploadThumbnail(labelId: string, file: File): Promise<Label | null> {
      try {
        const form = new FormData();
        form.append('file', file);
        const { data } = await api.post<Label>(`/labels/${labelId}/thumbnail`, form, { headers: { 'Content-Type': 'multipart/form-data' } });
        this.labels = this.labels.map((l) => (l.id === labelId ? data : l));
        return data;
      } catch (err) {
        const msg = axios.isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : err instanceof Error ? err.message : 'Failed to upload thumbnail';
        this.error = msg; return null;
      }
    },
  },
});
