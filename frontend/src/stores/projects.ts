import axios from 'axios';
import { defineStore } from 'pinia';

export type ProjectStage =
  | 'upload'
  | 'trim'
  | 'manual_labeling'
  | 'propagation'
  | 'validation'
  | 'export';

export interface Project {
  id: string;
  name: string;
  active: boolean;
  video_path?: string | null;
  trim_start?: number | null;
  trim_end?: number | null;
  stage: ProjectStage;
  locked_by?: string | null;
  created_at: string;
  updated_at: string;
}

interface ProjectListResponse {
  projects: Project[];
  total: number;
}

const api = axios.create({
  // Prefer explicit API URL when provided by environment (Docker dev: VITE_API_URL=http://backend:8000/api/v1)
  // Otherwise use relative path for Vite proxy in local dev.
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1',
  timeout: 8000,
});

export const useProjectsStore = defineStore('projects', {
  state: () => ({
    projects: [] as Project[],
    total: 0,
    loading: false,
    error: '' as string,
  }),
  actions: {
    async fetchProjects(): Promise<void> {
      this.loading = true;
      this.error = '';
      try {
        const { data } = await api.get<ProjectListResponse>('/projects');
        this.projects = data?.projects ?? [];
        this.total = data?.total ?? this.projects.length;
      } catch (err) {
        const message =
          axios.isAxiosError(err) && err.response?.data?.detail
            ? String(err.response.data.detail)
            : err instanceof Error
              ? err.message
              : 'Unable to load projects';
        this.error = message;
      } finally {
        this.loading = false;
      }
    },
    async createProject(name: string, active = true): Promise<Project | null> {
      try {
        const { data } = await api.post<Project>('/projects', { name, active });
        if (data) {
          // Optimistically add to list at top
          this.projects = [data, ...this.projects];
          this.total += 1;
          return data;
        }
        return null;
      } catch (err) {
        const message =
          axios.isAxiosError(err) && err.response?.data?.detail
            ? String(err.response.data.detail)
            : err instanceof Error
              ? err.message
              : 'Failed to create project';
        this.error = message;
        return null;
      }
    },
  },
  getters: {
    activeProjects: (state): Project[] => state.projects.filter((p) => p.active),
  },
});
