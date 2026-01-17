import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router';

const Home = () => import('../pages/Home.vue');
const Settings = () => import('../pages/Settings.vue');
const Upload = () => import('../pages/Upload.vue');
const Trim = () => import('../pages/Trim.vue');
const Labels = () => import('../pages/Labels.vue');
const ManualLabeling = () => import('../pages/ManualLabeling.vue');
const Propagation = () => import('../pages/Propagation.vue');

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'Home', component: Home },
  { path: '/settings', name: 'Settings', component: Settings },
  { path: '/labels', name: 'Labels', component: Labels },
  { path: '/projects/:id/upload', name: 'Upload', component: Upload },
  { path: '/projects/:id/trim', name: 'Trim', component: Trim },
  { path: '/projects/:id/manual-labeling', name: 'ManualLabeling', component: ManualLabeling },
  { path: '/projects/:id/validation', name: 'Validation', component: ManualLabeling },
  { path: '/projects/:id/propagation', name: 'Propagation', component: Propagation },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
