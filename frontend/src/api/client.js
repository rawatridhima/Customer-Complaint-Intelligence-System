import axios from 'axios';

// The token lives in localStorage so a page refresh keeps you signed in.
// Trade-off: any script running on the page could read it, so the app must
// never render untrusted HTML (React escapes text by default).
export const TOKEN_KEY = 'token';

export const client = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

client.interceptors.response.use(
  (r) => r,
  (err) => {
    // A 401 from the login form just means a wrong password. A 401 anywhere
    // else means the session expired or the account was disabled (FR-40):
    // tell AuthProvider, which clears the session and shows the login page.
    const isLoginCall = err.config?.url?.startsWith('/auth/login');
    if (err.response?.status === 401 && !isLoginCall) {
      window.dispatchEvent(new Event('auth:expired'));
    }
    return Promise.reject(err);
  }
);

// Pull the API's error message out of an axios error, for display.
export const errorMessage = (err, fallback = 'Something went wrong.') =>
  err?.response?.data?.error?.message ?? fallback;
