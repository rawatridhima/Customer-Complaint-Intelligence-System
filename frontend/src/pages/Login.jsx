import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { errorMessage } from '../api/client';

export default function Login() {
  const { login, status, expired } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const destination = location.state?.from?.pathname ?? '/';

  if (status === 'signed_in') return <Navigate to={destination} replace />;

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      navigate(destination, { replace: true });
    } catch (err) {
      setError(errorMessage(err, 'Could not reach the API. Is the backend running?'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto mt-16 max-w-sm">
      <h1 className="mb-1 text-2xl font-semibold">Sign in</h1>
      <p className="mb-8 text-sm text-muted">Support team access.</p>

      {expired && !error && (
        <p className="mb-4 border border-rule p-3 text-sm">
          Your session ended. Please sign in again.
        </p>
      )}

      <form onSubmit={onSubmit} className="space-y-4">
        <label className="block">
          <span className="mb-1 block text-xs text-muted">Username</span>
          <input
            className="w-full border border-rule bg-white px-3 py-2 text-sm outline-none focus:border-ink"
            autoComplete="username"
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-muted">Password</span>
          <input
            type="password"
            className="w-full border border-rule bg-white px-3 py-2 text-sm outline-none focus:border-ink"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>

        {error && (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-ink px-3 py-2 text-sm text-paper disabled:opacity-50"
        >
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>

      {import.meta.env.DEV && (
        <p className="mt-8 font-mono text-xs text-muted">
          dev accounts (after make seed): agent / manager / admin, password
          &lt;name&gt;-demo-pass
        </p>
      )}
    </div>
  );
}
