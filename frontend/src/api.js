import axios from 'axios';
import { toast } from 'react-toastify';

/**
 * @description Creates a centralized axios instance for all API calls.
 * In development, it targets the Flask server directly on port 5001.
 */
const apiClient = axios.create({
    // CORRECTED: The baseURL now points directly to the backend server, bypassing the proxy.
    baseURL: process.env.NODE_ENV === 'production' 
      ? '' 
      : 'http://localhost:5001',
    withCredentials: true,
});

// Add a response interceptor for global error handling
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

