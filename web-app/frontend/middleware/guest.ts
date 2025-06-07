export default defineNuxtRouteMiddleware((to) => {
  // Only run on client side
  if (process.server) return

  const isAuthenticated = process.client && !!useCookie('auth_token').value

  if (isAuthenticated) {
    return navigateTo('/dashboard')
  }
})