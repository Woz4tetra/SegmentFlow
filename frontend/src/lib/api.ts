const resolveApiBaseUrl = (): string => {
  const configured = import.meta.env.VITE_API_URL?.trim();
  if (configured) {
    return configured.replace(/\/+$/, '');
  }

  if (typeof window !== 'undefined') {
    return `${window.location.origin}/api/v1`;
  }

  return '/api/v1';
};

export const API_BASE_URL = resolveApiBaseUrl();

export const buildApiUrl = (path: string): string => {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalized}`;
};

export const buildWebSocketUrl = (path: string): string => {
  const httpUrl = buildApiUrl(path);
  const url = new URL(
    httpUrl,
    typeof window !== 'undefined' ? window.location.origin : 'http://localhost'
  );
  const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${url.host}${url.pathname}${url.search}`;
};
