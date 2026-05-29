import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue')
  },
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue')
  },
  {
    path: '/heatmap',
    name: 'Heatmap',
    component: () => import('@/views/Heatmap.vue')
  },
  {
    path: '/scatter',
    name: 'Scatter',
    component: () => import('@/views/Scatter.vue')
  },
  {
    path: '/detail/:code',
    name: 'Detail',
    component: () => import('@/views/Detail.vue')
  },
  {
    path: '/control',
    name: 'Control',
    component: () => import('@/views/Control.vue')
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue')
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
