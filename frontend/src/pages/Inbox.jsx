import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { listComplaints } from '../api/complaints';
import PriorityBadge from '../components/PriorityBadge';

const FILTERS = ['all', 'new', 'in_review', 'resolved'];

export default function Inbox() {
  const [status, setStatus] = useState('all');
  const { data, isLoading, error } = useQuery({
    queryKey: ['complaints', status],
    queryFn: () => listComplaints(status === 'all' ? {} : { status }),
    refetchInterval: 5000,
  });

  if (error) {
    return (
      <p className="text-sm">
        Could not reach the API. Check that the backend container is running.
      </p>
    );
  }

  return (
    <div>
      <div className="mb-6 flex items-baseline justify-between border-b border-rule pb-3">
        <h1 className="text-2xl font-semibold">Inbox</h1>
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setStatus(f)}
              className={`px-3 py-1 text-sm ${
                status === f ? 'bg-ink text-paper' : 'text-muted hover:text-ink'
              }`}
            >
              {f.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {isLoading && <p className="text-sm text-muted">Loading complaints…</p>}

      {data?.items?.length === 0 && (
        <div className="border border-rule p-8 text-center">
          <p className="mb-2">No complaints yet.</p>
          <p className="text-sm text-muted">
            Run <code className="font-mono">make seed</code> to load sample data.
          </p>
        </div>
      )}

      {data?.items?.length > 0 && (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-xs text-muted">
              <th className="pb-2 font-medium">Complaint</th>
              <th className="pb-2 font-medium">Category</th>
              <th className="pb-2 font-medium">Sentiment</th>
              <th className="pb-2 font-medium">Priority</th>
              <th className="pb-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((c) => (
              <tr key={c.complaint_id} className="border-b border-rule/60 hover:bg-white">
                <td className="max-w-md truncate py-3 pr-6">
                  <Link to={`/complaints/${c.complaint_id}`} className="hover:underline">
                    {c.raw_text}
                  </Link>
                </td>
                <td className="py-3 pr-6 text-muted">
                  {c.prediction?.category?.replace('_', ' ') ?? 'analysing…'}
                </td>
                <td className="py-3 pr-6 text-muted">{c.prediction?.sentiment_label ?? '—'}</td>
                <td className="py-3 pr-6">
                  <PriorityBadge bucket={c.prediction?.priority_bucket} />
                </td>
                <td className="py-3 text-muted">{c.status.replace('_', ' ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
