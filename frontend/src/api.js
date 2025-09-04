import axios from 'axios';
import { toast } from 'react-toastify';

const apiClient = axios.create({
    baseURL: process.env.NODE_ENV === 'production' 
      ? '' 
      : 'http://localhost:5001',
    withCredentials: true,
});

// Request interceptor to add the JWT token to headers
apiClient.interceptors.request.use(
    (config) => {
        const authData = localStorage.getItem('auth');
        if (authData) {
            const { token } = JSON.parse(authData);
            if (token) {
                config.headers['Authorization'] = `Bearer ${token}`;
            }
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Response interceptor for global error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      console.error("Authentication Error:", error.response);
      toast.error("Session expired. Please log in again.");
      // Future logic to handle automatic logout could go here.
    }
    return Promise.reject(error);
  }
);

export default apiClient;

