import axios from 'axios';

// ============================================================================
// API BASE URL CONFIGURATION
// Configured dynamically from environment variable VITE_API_URL.
// ============================================================================
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ============================================================================
// SECURITY ARCHITECTURE NOTE: TOKEN STORAGE IN LOCALSTORAGE
// ----------------------------------------------------------------------------
// Finding: JWT access tokens are stored in `localStorage` ('homejoy_token').
// Assessment: For this academic prototype / college capstone project, localStorage
// provides convenient client-side session persistence without cross-origin cookie
// configuration complexities.
// Production Recommendation: Storing tokens in localStorage is susceptible to
// theft if a Cross-Site Scripting (XSS) vulnerability exists. For enterprise /
// HIPAA compliance, authentication tokens should be stored in HttpOnly, Secure,
// SameSite=Strict cookies with CSRF tokens or maintained in-memory with short-lived
// access tokens and refresh token rotation.
// ============================================================================

// Request Interceptor: Attach JWT Token if available
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('homejoy_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor: Format errors and handle Unauthorized errors globally
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // If token expired or invalid, clear local storage
      localStorage.removeItem('homejoy_token');
      localStorage.removeItem('homejoy_user');
    }

    // Normalize FastAPI / Pydantic validation errors (HTTP 422 or any status)
    // Converts array of error objects [{type, loc, msg, input, ctx}] into human-readable strings
    if (error.response && error.response.data) {
      const { detail } = error.response.data;
      if (Array.isArray(detail)) {
        const formatted = detail
          .map((item) => {
            if (typeof item === 'string') return item;
            if (item && typeof item === 'object') {
              const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : '';
              const cleanMsg = item.msg ? String(item.msg).replace(/^Value error,\s*/i, '') : 'Invalid value';
              return field && field !== 'body' ? `${field}: ${cleanMsg}` : cleanMsg;
            }
            return String(item);
          })
          .filter(Boolean)
          .join('; ');
        error.response.data.detail = formatted || 'Validation error. Please verify your input.';
      } else if (detail && typeof detail === 'object') {
        error.response.data.detail = detail.msg || detail.message || JSON.stringify(detail);
      }
    }

    return Promise.reject(error);
  }
);

export default api;
