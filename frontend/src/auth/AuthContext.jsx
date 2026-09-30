import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { getMe, login as loginRequest } from '../api/auth';
import { TOKEN_KEY } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState(null);
  // 'checking' while a stored token is validated on page load, so the app
  // does not flash the login page for someone who is already signed in.
  const [status, setStatus] = useState(
    localStorage.getItem(TOKEN_KEY) ? 'checking' : 'signed_out'
  );
  const [expired, setExpired] = useState(false);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    queryClient.clear(); // never show one user's cached data to the next
    setUser(null);
    setStatus('signed_out');
  }, [queryClient]);

  // Restore the session on page load.
  useEffect(() => {
    if (status !== 'checking') return;
    getMe()
      .then((me) => {
        setUser(me);
        setStatus('signed_in');
      })
      .catch(logout);
  }, [status, logout]);

  // Any 401 from the API (expired token, disabled account) ends the session.
  useEffect(() => {
    const onExpired = () => {
      setExpired(true);
      logout();
    };
    window.addEventListener('auth:expired', onExpired);
    return () => window.removeEventListener('auth:expired', onExpired);
  }, [logout]);

  const login = useCallback(async (username, password) => {
    const { access_token, user: me } = await loginRequest(username, password);
    localStorage.setItem(TOKEN_KEY, access_token);
    setExpired(false);
    setUser(me);
    setStatus('signed_in');
    return me;
  }, []);

  const value = useMemo(
    () => ({
      user,
      status,
      expired,
      login,
      logout,
      hasRole: (...roles) => Boolean(user && roles.includes(user.role)),
    }),
    [user, status, expired, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
