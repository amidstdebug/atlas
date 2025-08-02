import axios, { type AxiosInstance } from 'axios'

export default defineNuxtPlugin(() => {
  const config = useRuntimeConfig()
  
  const api: AxiosInstance = axios.create({
    baseURL: config.public.baseURL,
    timeout: 60000,
    headers: {
      'Content-Type': 'application/json'
    }
  })

  // Request interceptor to add auth token
  api.interceptors.request.use((config) => {
    const authCookie = useCookie('auth_token')
    const token = authCookie.value
    
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    
    return config
  })

  // Response interceptor for error handling
  api.interceptors.response.use(
    (response) => response,
    async (error) => {
      if (error.response?.status === 401) {
        // Token expired, try to refresh
        const authStore = useAuthStore()
        const refreshed = await authStore.refreshToken()
        
        if (!refreshed) {
          // Refresh failed, redirect to login
          await navigateTo('/login')
        } else {
          // Retry original request with new token
          return api.request(error.config)
        }
      }
      
      return Promise.reject(error)
    }
  )

  // Transcription API methods
  const transcribeAudio = async (audioBlob: Blob, prompt?: string) => {
    const formData = new FormData()
    formData.append('file', audioBlob, 'audio.webm')
    if (prompt) {
      formData.append('prompt', prompt)
    }

    const response = await api.post('/transcribe', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })

    return response.data
  }

  return {
    provide: {
      api,
      transcribeAudio
    }
  }
})