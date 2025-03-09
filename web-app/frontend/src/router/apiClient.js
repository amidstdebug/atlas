import axios from 'axios';
import Cookies from 'js-cookie';
import router from './router'; // Assuming you have your router setup

// Create an Axios instance
const apiClient = axios.create({
  baseURL: 'http://localhost:5002/', // Your API base URL
//   baseURL: 'https://jwong.dev/api/'
});

// Login helper function to get JWT token
export async function login(userId, password) {
  try {
    const response = await apiClient.post('/auth/login', { 
      user_id: userId, 
      password: password 
    });
    
    if (response.data && response.data.token) {
      Cookies.set('auth_token', response.data.token);
      apiClient.defaults.headers['Authorization'] = `Bearer ${response.data.token}`;
      return { success: true };
    } else {
      return {
        success: false, 
        error: 'Invalid response from server' 
      };
    }
  } catch (error) {
    console.error('Login failed:', error);
    return { 
      success: false, 
      error: error.response?.data?.detail || 'Login failed' 
    };
  }
}

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

    // Handle 504 Gateway Timeout: retry the same request once
    if (error.response && error.response.status === 504 && !originalRequest._retry504) {
      console.log("504 RETRY")
      originalRequest._retry504 = true; // mark request to avoid infinite loop
      return apiClient(originalRequest); // retry the request once
    }

    // Handle token expiration
    if (error.response && (error.response.status === 401 || error.response.status === 403) && !originalRequest._retry) {
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

let loadingStatus = { loading: false, error: null, success: null };

apiClient.interceptors.request.use(
  config => {
    loadingStatus.loading = true;
    loadingStatus.error = null;
    loadingStatus.success = null;
    return config;
  },
  error => {
    loadingStatus.loading = false;
    return Promise.reject(error);
  }
);

apiClient.interceptors.response.use(
  response => {
    loadingStatus.loading = false;
    loadingStatus.success = true;
    return response;
  },
  error => {
    loadingStatus.loading = false;
    loadingStatus.error = error && error.response && error.response.data ? error.response.data.detail : error.message;
    return Promise.reject(error);
  }
);

export function getLoadingStatus() {
  return loadingStatus;
}

export default apiClient;
