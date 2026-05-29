/**
 * Axios-based API client configured to communicate with the Django backend.
 *
 * Base URL is read from the VITE_API_BASE_URL environment variable, falling
 * back to '/api/v1' so that the Vite dev-server proxy (configured in
 * vite.config.ts) forwards requests to http://localhost:8000.
 *
 * Authentication: bearer token stored in localStorage under the key
 * 'auth_token'.  The request interceptor attaches it automatically.
 * CSRF: Django's csrftoken cookie is read and forwarded as the
 * X-CSRFToken header on all mutating requests (POST, PUT, PATCH, DELETE).
 * The response interceptor redirects to /login on 401 responses.
 */

import axios, {
  type AxiosInstance,
  type InternalAxiosRequestConfig,
  type AxiosResponse,
  type AxiosError,
} from 'axios';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

/** Read a cookie value by name (used to extract Django's csrftoken). */
function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[1]) : null;
}

const CSRF_SAFE_METHODS = new Set(['get', 'head', 'options', 'trace']);

const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // send session cookies for Django session auth
});

// ─── Request interceptor: attach bearer token + CSRF header ──────────────────
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Bearer token (used by the travel ingestion API endpoint)
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // CSRF token for Django's CsrfViewMiddleware on mutating requests
    const method = (config.method ?? 'get').toLowerCase();
    if (!CSRF_SAFE_METHODS.has(method)) {
      const csrfToken = getCookie('csrftoken');
      if (csrfToken) {
        config.headers['X-CSRFToken'] = csrfToken;
      }
    }

    return config;
  },
  (error: AxiosError) => Promise.reject(error),
);

// ─── Response interceptor: handle 401 globally ───────────────────────────────
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      // Redirect to login page if not already there
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

export default apiClient;
