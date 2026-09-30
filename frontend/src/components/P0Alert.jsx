import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { listComplaints } from '../api/complaints';
import { useAuth } from '../auth/AuthContext';

// FR-18: a visible alert whenever a complaint is scored P0.
//
// Polls for P0 complaints that are still new. Each user dismisses the ones
// they have seen; the dismissed ids are kept in localStorage so the banner
// does not come back on refresh, but any new P0 brings it back.
const storageKey = (userId) => `p0-seen:${userId}`;

function loadSeen(userId) {
  try {
    return new Set(JSON.parse(localStorage.getItem(storageKey(userId)) ?? '[]'));
  } catch {
    return new Set();
  }
}

export default function P0Alert() {
  const { user } = useAuth();
  const [seen, setSeen] = useState(() => loadSeen(user.user_id));

  useEffect(() => setSeen(loadSeen(user.user_id)), [user.user_id]);

  const { data } = useQuery({
    queryKey: ['p0-alert'],
    queryFn: () => listComplaints({ priority: 'P0', status: 'new', size: 20 }),
    refetchInterval: 5000,
  });

  const unseen = (data?.items ?? []).filter((c) => !seen.has(c.complaint_id));
  if (unseen.length === 0) return null;

  const dismiss = () => {
    // Keep only ids that are still P0 and new, so the list does not grow forever.
    const next = new Set((data?.items ?? []).map((c) => c.complaint_id));
    localStorage.setItem(storageKey(user.user_id), JSON.stringify([...next]));
    setSeen(next);
  };

  return (
    <div
      role="alert"
      className="mb-8 flex items-start gap-4 border-2 border-red-700 bg-red-50 p-4 text-red-900"
    >
      <span aria-hidden="true" className="font-mono">▲▲</span>
      <div className="flex-1">
        <p className="font-medium">
          {unseen.length === 1
            ? '1 new P0 complaint needs attention'
            : `${unseen.length} new P0 complaints need attention`}
        </p>
        <ul className="mt-2 space-y-1 text-sm">
          {unseen.slice(0, 3).map((c) => (
            <li key={c.complaint_id} className="truncate">
              <Link to={`/complaints/${c.complaint_id}`} className="underline">
                {c.raw_text}
              </Link>
            </li>
          ))}
          {unseen.length > 3 && <li>and {unseen.length - 3} more</li>}
        </ul>
      </div>
      <button onClick={dismiss} className="text-sm underline">
        Dismiss
      </button>
    </div>
  );
}
