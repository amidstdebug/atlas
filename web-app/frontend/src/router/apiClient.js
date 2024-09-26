import axios from 'axios';
import Cookies from 'js-cookie';
import router from './router'; // Assuming you have your router setup

// Create an Axios instance
const apiClient = axios.create({
  baseURL: 'http://localhost:5000/', // Your API base URL
});

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });

  failedQueue = [];
};

// Request interceptor to add the token to the headers
apiClient.interceptors.request.use(config => {
  const token = Cookies.get('auth_token');

  // Check if the request URL is not for the /login endpoint
  if (token && !config.url.includes('/login')) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }

  return config;
}, error => {
  return Promise.reject(error);
});


// Response interceptor to handle expired tokens
apiClient.interceptors.response.use(
  response => response,
  async error => {
    const originalRequest = error.config;

    // Handle token expiration
    if ((error.response.status === 401 || error.response.status === 403) && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(token => {
          originalRequest.headers['Authorization'] = `Bearer ${token}`;
          return apiClient(originalRequest);
        }).catch(err => {
          return Promise.reject(err);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      return new Promise((resolve, reject) => {
        apiClient.post('/auth/refresh', null, {
          headers: {
            'Authorization': `Bearer ${Cookies.get('auth_token')}`
          }
        }) // Adjust to your refresh token endpoint
          .then(({ data }) => {
            Cookies.set('auth_token', data.token);
            apiClient.defaults.headers['Authorization'] = `Bearer ${data.token}`;
            originalRequest.headers['Authorization'] = `Bearer ${data.token}`;
            processQueue(null, data.token);
            resolve(apiClient(originalRequest));
          })
          .catch(err => {
            processQueue(err, null);
            if (error.response.status === 403) {
              // Token is no longer secure, clear it and redirect to login
              Cookies.remove('auth_token');
              router.push('/login');
            }
            reject(err);
          })
          .finally(() => {
            isRefreshing = false;
          });
      });
    }

    return Promise.reject(error);
  }
);

export default apiClient;
