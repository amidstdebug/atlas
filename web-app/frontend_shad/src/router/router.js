import { createRouter, createWebHistory } from 'vue-router'
// import MainApp from '@/components/MainApp.vue'
import LoginPage from '@/components/LoginPage.vue'
import Cookies from 'js-cookie'
import MainApp from "@/components/MainApp.vue";

const routes = [
  {
    path: '/',
    name: 'Home',
    component: MainApp,
    // meta: { requiresAuth: true }
  },
  {
    path: '/login',
    name: 'Login',
    component: LoginPage
  }
]

const router = createRouter({
  history: createWebHistory('/'),
  routes
})

// TODO: REMOVE THESE COMMENTS
// router.beforeEach((to, from, next) => {
//   const token = Cookies.get('auth_token')
//   if (to.matched.some(record => record.meta.requiresAuth) && !token) {
//     next('/login')
//   } else {
//     next()
//   }
// })

export default router