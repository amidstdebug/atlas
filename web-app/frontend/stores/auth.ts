import { defineStore } from 'pinia'

export interface User {
  id: number
  username: string
}

export interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: false
  }),

  getters: {
    currentUser: (state) => state.user,
    isLoggedIn: (state) => state.isAuthenticated && !!state.token
  },

  actions: {
    async login(credentials: { user_id: string; password: string }) {
      this.isLoading = true

      try {
        const { $api } = useNuxtApp()
        const response = await $api.post('/auth/login', credentials)

        // Handle different response structures - check both locations
        const token = response.data?.token || response.data?.data?.token
        const user = response.data?.user || response.data?.data?.user

        if (token) {
          this.token = token
          this.user = user
          this.isAuthenticated = true

          // Store token in cookie
          const authCookie = useCookie<string | null>('auth_token', {
            default: () => null,
            maxAge: 60 * 60 * 24 * 7 // 7 days
          })
          authCookie.value = this.token

          // Store user data in cookie
          const userCookie = useCookie<User | null>('auth_user', {
            default: () => null,
            maxAge: 60 * 60 * 24 * 7 // 7 days
          })
          userCookie.value = user

          // Only fetch user if we don't have user data from login response
          if (!user) {
            await this.fetchUser()
          }

          return { success: true }
        } else {
          return {
            success: false,
            error: 'No token received from server'
          }
        }
      } catch (error: any) {
        console.error('Login error:', error)
        return {
          success: false,
          error: error.response?.data?.detail || error.response?.data?.message || 'Login failed'
        }
      } finally {
        this.isLoading = false
      }
    },

    async logout() {
      this.user = null
      this.token = null
      this.isAuthenticated = false

      // Clear cookies
      const authCookie = useCookie('auth_token')
      const userCookie = useCookie('auth_user')
      authCookie.value = null
      userCookie.value = null

      await navigateTo('/login')
    },

    async refreshToken() {
      if (!this.token) return false

      try {
        const { $api } = useNuxtApp()
        const response = await $api.post('/auth/refresh')

        // Handle different response structures
        const token = response.data?.token || response.data?.data?.token

        if (token) {
          this.token = token

          // Update cookie
          const authCookie = useCookie('auth_token')
          authCookie.value = this.token

          return true
        } else {
          await this.logout()
          return false
        }
      } catch (error) {
        console.error('Token refresh error:', error)
        await this.logout()
        return false
      }
    },

    async fetchUser() {
      if (!this.token) return

      try {
        const { $api } = useNuxtApp()
        // const response = await $api.get('/users/me')
        // if (response.data) {
        //   this.user = response.data
        // }
      } catch (error) {
        console.error('Failed to fetch user:', error)
        await this.logout()
      }
    },

    async checkAuth() {
      const authCookie = useCookie('auth_token')
      const userCookie = useCookie<User | null>('auth_user')
      const token = authCookie.value
      const user = userCookie.value

      if (token) {
        this.token = token
        this.user = user
        this.isAuthenticated = true
        // Note: In a real app, you'd validate the token with the server
        // Only fetch user if we don't have user data from cookie
        if (!user) {
          await this.fetchUser()
        }
      } else {
        // Ensure clean state if no token
        this.user = null
        this.token = null
        this.isAuthenticated = false
      }
    }
  }
})