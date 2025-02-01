import axios from 'axios'
import Cookies from 'js-cookie'
import router from '@/router/router'

const apiClient = axios.create({
  baseURL: 'http://localhost:5001/'
})

let isRefreshing = false
let failedQueue = []

const processQueue = (error, token = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token)
    }
  })
  failedQueue = []
}

apiClient.interceptors.request.use(config => {
  const token = Cookies.get('auth_token')
  if (token && !config.url.includes('/login')) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
}, error => Promise.reject(error))

apiClient.interceptors.response.use(
  response => response,
  async error => {
    const originalRequest = error.config
    if (error.response && error.response.status === 504 && !originalRequest._retry504) {
      originalRequest._retry504 = true
      return apiClient(originalRequest)
    }
    if (error.response && (error.response.status === 401 || error.response.status === 403) && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then(token => {
          originalRequest.headers['Authorization'] = `Bearer ${token}`
          return apiClient(originalRequest)
        }).catch(err => Promise.reject(err))
      }
      originalRequest._retry = true
      isRefreshing = true
      return new Promise((resolve, reject) => {
        apiClient.post('/auth/refresh', null, {
          headers: {
            'Authorization': `Bearer ${Cookies.get('auth_token')}`
          }
        }).then(({ data }) => {
          Cookies.set('auth_token', data.token)
          apiClient.defaults.headers['Authorization'] = `Bearer ${data.token}`
          originalRequest.headers['Authorization'] = `Bearer ${data.token}`
          processQueue(null, data.token)
          resolve(apiClient(originalRequest))
        }).catch(err => {
          processQueue(err, null)
          if (error.response.status === 403) {
            Cookies.remove('auth_token')
            router.push('/login')
          }
          reject(err)
        }).finally(() => {
          isRefreshing = false
        })
      })
    }
    return Promise.reject(error)
  }
)

export default apiClient