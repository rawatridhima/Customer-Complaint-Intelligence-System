import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';

// Wraps pages that need a signed-in user, optionally with specific roles.
// The server enforces the same rules; this only decides what to render.
export default function RequireAuth({ roles, children }) {
  const { status, hasRole } = useAuth();
  const location = useLocation();

  if (status === 'checking') {
    return <p className="text-sm text-muted">Checking your session…</p>;
  }
  if (status !== 'signed_in') {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (roles && !hasRole(...roles)) {
    return (
      <div className="border border-rule p-8">
        <p className="mb-1 font-medium">You don't have access to this page.</p>
        <p className="text-sm text-muted">It needs the role: {roles.join(' or ')}.</p>
      </div>
    );
  }
  return children;
}
