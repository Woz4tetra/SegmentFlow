import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router';

const Home = () => import('../pages/Home.vue');
const Settings = () => import('../pages/Settings.vue');
const Upload = () => import('../pages/Upload.vue');
const Trim = () => import('../pages/Trim.vue');

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'Home', component: Home },
  { path: '/settings', name: 'Settings', component: Settings },
  { path: '/projects/:id/upload', name: 'Upload', component: Upload },
  { path: '/projects/:id/trim', name: 'Trim', component: Trim },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
