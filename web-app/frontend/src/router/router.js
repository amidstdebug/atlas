import { createRouter, createWebHistory } from 'vue-router';
import MainApp from '../components/MainApp.vue';
import LoginPage from '../components/LoginPage.vue';
import Cookies from 'js-cookie';

const routes = [
  {
    path: '/',
    name: 'Home',
    component: MainApp,
    meta: { requiresAuth: false },
  },
  {
    path: '/login',
    name: 'Login',
    component: LoginPage,
  },
];

const router = createRouter({
  history: createWebHistory('/atlas/'), // Match your publicPath
  routes,
});

// Navigation Guard to check authentication
router.beforeEach((to, from, next) => {
  const token = Cookies.get('auth_token');
  if (to.matched.some(record => record.meta.requiresAuth) && !token) {
    next('/login');
  } else {
    next();
  }
});

export default router;