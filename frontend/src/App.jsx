import { Routes, Route, Link } from 'react-router-dom';
import Inbox from './pages/Inbox';
import ComplaintDetail from './pages/ComplaintDetail';
import Login from './pages/Login';
import RequireAuth from './auth/RequireAuth';
import { useAuth } from './auth/AuthContext';
import P0Alert from './components/P0Alert';

function Header() {
  const { user, logout } = useAuth();
  return (
    <header className="mb-10 flex items-baseline gap-6">
      <Link to="/" className="font-mono text-sm tracking-tight">
        complaint intelligence
      </Link>
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

export default function App() {
  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <Header />
      <SignedInOnly>
        <P0Alert />
      </SignedInOnly>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Inbox />
            </RequireAuth>
          }
        />
        <Route
          path="/complaints/:id"
          element={
            <RequireAuth>
              <ComplaintDetail />
            </RequireAuth>
          }
        />
      </Routes>
    </div>
  );
}
