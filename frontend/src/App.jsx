import { Routes, Route, Link } from 'react-router-dom';
import Inbox from './pages/Inbox';
import ComplaintDetail from './pages/ComplaintDetail';

export default function App() {
  return (
    <div className="mx-auto max-w-6xl px-8 py-10">
      <header className="mb-10 flex items-baseline gap-6">
        <Link to="/" className="font-mono text-sm tracking-tight">
          complaint intelligence
        </Link>
        <span className="font-mono text-xs text-muted">skeleton build</span>
      </header>

      <Routes>
        <Route path="/" element={<Inbox />} />
        <Route path="/complaints/:id" element={<ComplaintDetail />} />
      </Routes>
    </div>
  );
}
