# SegmentFlow Frontend

Vue 3 + Vite app with Pinia and Vue Router.

## Scripts

- `npm install`: Install dependencies
- `npm run dev`: Start dev server (http://localhost:5173)
- `npm run build`: Build for production
- `npm run preview`: Preview built app locally

## Structure

- `src/main.ts`: App entry; mounts Pinia + Router
- `src/router/`: Client routes
- `src/stores/`: Pinia stores
- `src/pages/`: Example pages (Home, Settings)
- `src/components/`: Shared UI components

## Backend Integration

API clients read `VITE_API_URL` when provided; otherwise they default to same-origin `/api/v1`. Set `VITE_API_URL` in Vite `.env` files or Docker build args to point at a remote backend URL that the browser can reach.