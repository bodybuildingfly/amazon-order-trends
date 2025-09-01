import axios from 'axios';
import { toast } from 'react-toastify';

/**
 * @description Creates a centralized axios instance for all API calls.
 */
const apiClient = axios.create({
    baseURL: process.env.NODE_ENV === 'production' 
      ? '' 
      : 'http://localhost:3000', // Proxy will handle this
    withCredentials: true,
});

// Add a response interceptor
apiClient.interceptors.response.use(
  (response) => {
    // Any status code that lie within the range of 2xx cause this function to trigger
    return response;
  },
  (error) => {
    // Any status codes that falls outside the range of 2xx cause this function to trigger
    // You can add global error handling here, e.g., for 401 Unauthorized
    if (error.response && error.response.status === 401) {
      // For example, redirect to login page or refresh token
      // For now, we just log and toast
      console.error("Authentication Error:", error.response);
      toast.error("Session expired. Please log in again.");
      // You might want to trigger a logout action here
    }
    return Promise.reject(error);
  }
);

export default apiClient;

