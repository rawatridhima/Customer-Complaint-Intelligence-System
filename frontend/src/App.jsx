import { lazy, Suspense } from 'react';
import { Routes, Route, Link, NavLink } from 'react-router-dom';
import Inbox from './pages/Inbox';
import ComplaintDetail from './pages/ComplaintDetail';
import Login from './pages/Login';
import Settings from './pages/Settings';
import Users from './pages/Users';
import RequireAuth from './auth/RequireAuth';
import { useAuth } from './auth/AuthContext';
import P0Alert from './components/P0Alert';

// The chart pages pull in the charting library, so they load on first visit
// instead of being part of every agent's download.
const Analytics = lazy(() => import('./pages/Analytics'));
const ModelHealth = lazy(() => import('./pages/ModelHealth'));

const MANAGERS = ['manager', 'admin'];
const ADMINS = ['admin'];

// Links shown per role. The API enforces the same rules (FR-38); hiding a
// link only keeps the screen tidy.
const NAV = [
  { to: '/', label: 'Inbox', end: true },
  { to: '/analytics', label: 'Analytics', roles: MANAGERS },
  { to: '/settings', label: 'Settings', roles: MANAGERS },
  { to: '/users', label: 'Users', roles: ADMINS },
];

function Header() {
  const { user, logout, hasRole } = useAuth();
  return (
    <header className="mb-10 flex flex-wrap items-baseline gap-x-6 gap-y-2">
      <Link to="/" className="font-mono text-sm tracking-tight">
        complaint intelligence
      </Link>
      {user && (
        <nav className="flex gap-4 text-sm">
          {NAV.filter((n) => !n.roles || hasRole(...n.roles)).map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) => (isActive ? 'text-ink underline underline-offset-4' : 'text-muted hover:text-ink')}
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
      )}
      {user && (
        <div className="ml-auto flex items-baseline gap-4 text-sm">
          <span>
            {user.username}{' '}
            <span className="font-mono text-xs text-muted">{user.role}</span>
          </span>
          <button onClick={logout} className="text-muted hover:text-ink">
            Sign out
          </button>
        </div>
      )}
    </header>
  );
}

function SignedInOnly({ children }) {
  const { status } = useAuth();
  return status === 'signed_in' ? children : null;
}

const page = (element, roles) => (
  <RequireAuth roles={roles}>
    <Suspense fallback={<p className="text-sm text-muted">Loading…</p>}>{element}</Suspense>
  </RequireAuth>
);

export default function App() {
  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <Header />
      <SignedInOnly>
        <P0Alert />
      </SignedInOnly>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={page(<Inbox />)} />
        <Route path="/complaints/:id" element={page(<ComplaintDetail />)} />
        <Route path="/analytics" element={page(<Analytics />, MANAGERS)} />
        <Route path="/analytics/model" element={page(<ModelHealth />, MANAGERS)} />
        <Route path="/settings" element={page(<Settings />, MANAGERS)} />
        <Route path="/users" element={page(<Users />, ADMINS)} />
      </Routes>
    </div>
  );
}
