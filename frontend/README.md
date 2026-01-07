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

Configure API clients (e.g., Axios) to hit the backend at http://localhost:8000 during local dev. Add environment variables later using Vite's `.env` files if needed.