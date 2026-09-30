import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useComplaint } from '../hooks/useComplaint';
import { useAuth } from '../auth/AuthContext';
import {
  assignComplaint,
  getHistory,
  overrideCategory,
  updateStatus,
} from '../api/complaints';
import { errorMessage } from '../api/client';
import PriorityBadge from '../components/PriorityBadge';
import ConfidenceBar from '../components/ConfidenceBar';
import PriorityBreakdown from '../components/PriorityBreakdown';
import AIField from '../components/AIField';
import { CATEGORIES, formatDateTime, humanize } from '../lib/format';

// A mutation that refreshes everything this page and the inbox show.
function useComplaintAction(id, fn) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (updated) => {
      queryClient.setQueryData(['complaint', id], updated);
      queryClient.invalidateQueries({ queryKey: ['history', id] });
      queryClient.invalidateQueries({ queryKey: ['complaints'] });
      queryClient.invalidateQueries({ queryKey: ['p0-alert'] });
    },
  });
}

function StatusControl({ complaint }) {
  const [next, setNext] = useState('');
  const action = useComplaintAction(complaint.complaint_id, (s) =>
    updateStatus(complaint.complaint_id, s)
  );
  const options = complaint.allowed_next_statuses;

  const apply = () => {
    // NFR-18: resolving is final in the state machine, so confirm it.
    if (next === 'resolved' && !window.confirm('Resolve this complaint? It cannot be reopened.')) return;
    action.mutate(next, { onSuccess: () => setNext('') });
  };

  return (
    <div>
      <h3 className="mb-1 text-sm font-medium text-muted">Status</h3>
      <p className="mb-2">{humanize(complaint.status)}</p>
      {options.length === 0 ? (
        <p className="text-xs text-muted">Final state, no further changes.</p>
      ) : (
        <div className="flex gap-2">
          <select
            value={next}
            onChange={(e) => setNext(e.target.value)}
            className="border border-rule bg-white px-2 py-1 text-sm"
          >
            <option value="">Move to…</option>
            {options.map((s) => (
              <option key={s} value={s}>
                {humanize(s)}
              </option>
            ))}
          </select>
          <button
            onClick={apply}
            disabled={!next || action.isPending}
            className="bg-ink px-3 py-1 text-sm text-paper disabled:opacity-40"
          >
            Update
          </button>
        </div>
      )}
      {action.error && <p className="mt-1 text-xs text-red-700">{errorMessage(action.error)}</p>}
    </div>
  );
}

function CategoryControl({ complaint }) {
  const p = complaint.prediction;
  const [editing, setEditing] = useState(false);
  const [choice, setChoice] = useState('');
  const action = useComplaintAction(complaint.complaint_id, (c) =>
    overrideCategory(complaint.complaint_id, c)
  );

  const save = () =>
    action.mutate(choice, {
      onSuccess: () => {
        setEditing(false);
        setChoice('');
      },
    });

  return (
    <div>
      <h3 className="mb-1 text-sm font-medium text-muted">Category</h3>
      <p className="mb-2">
        {humanize(p.category)}
        {p.original_category && (
          <span className="ml-2 font-mono text-xs text-muted">
            corrected, model said {humanize(p.original_category)}
          </span>
        )}
      </p>
      {!p.original_category && (
        <ConfidenceBar value={Number(p.category_confidence)} needsReview={p.needs_review} />
      )}

      {editing ? (
        <div className="mt-2 flex gap-2">
          <select
            value={choice}
            onChange={(e) => setChoice(e.target.value)}
            className="border border-rule bg-white px-2 py-1 text-sm"
            autoFocus
          >
            <option value="">Correct category…</option>
            {CATEGORIES.filter((c) => c !== p.category).map((c) => (
              <option key={c} value={c}>
                {humanize(c)}
              </option>
            ))}
          </select>
          <button
            onClick={save}
            disabled={!choice || action.isPending}
            className="bg-ink px-3 py-1 text-sm text-paper disabled:opacity-40"
          >
            Save
          </button>
          <button onClick={() => setEditing(false)} className="text-sm text-muted">
            Cancel
          </button>
        </div>
      ) : (
        <button onClick={() => setEditing(true)} className="mt-2 text-xs text-muted underline hover:text-ink">
          Wrong category? Correct it
        </button>
      )}
      {action.error && <p className="mt-1 text-xs text-red-700">{errorMessage(action.error)}</p>}
    </div>
  );
}

function AssigneeControl({ complaint }) {
  const { user } = useAuth();
  const action = useComplaintAction(complaint.complaint_id, (userId) =>
    assignComplaint(complaint.complaint_id, userId)
  );
  const mine = complaint.assigned_to === user.user_id;

  return (
    <div>
      <h3 className="mb-1 text-sm font-medium text-muted">Assigned to</h3>
      <p className="mb-2">{mine ? 'you' : complaint.assigned_to ? 'another agent' : 'nobody'}</p>
      <button
        onClick={() => action.mutate(mine ? null : user.user_id)}
        disabled={action.isPending}
        className="text-xs text-muted underline hover:text-ink"
      >
        {mine ? 'Unassign' : 'Assign to me'}
      </button>
      {action.error && <p className="mt-1 text-xs text-red-700">{errorMessage(action.error)}</p>}
    </div>
  );
}

function describe(entry) {
  const d = entry.details ?? {};
  switch (entry.action) {
    case 'status_changed':
      return `moved from ${humanize(d.from)} to ${humanize(d.to)}${d.bulk ? ' (bulk)' : ''}`;
    case 'category_overridden':
      return `changed category from ${humanize(d.from)} to ${humanize(d.to)}` +
        (d.priority_from !== d.priority_to ? `, priority ${d.priority_from} → ${d.priority_to}` : '');
    case 'assigned':
      return d.to ? `assigned to ${d.to}` : 'unassigned';
    case 'response_approved':
      return `approved the response${d.edited ? ' after editing' : ''}`;
    default:
      return humanize(entry.action);
  }
}

function History({ id }) {
  const { data } = useQuery({ queryKey: ['history', id], queryFn: () => getHistory(id) });
  if (!data) return null;
  return (
    <section>
      <h2 className="mb-3 text-sm font-medium text-muted">History</h2>
      {data.length === 0 ? (
        <p className="text-sm text-muted">No actions yet.</p>
      ) : (
        <ol className="space-y-2 text-sm">
          {data.map((h, i) => (
            <li key={i} className="flex gap-3">
              <span className="w-40 shrink-0 font-mono text-xs text-muted">{formatDateTime(h.created_at)}</span>
              <span>
                <span className="font-medium">{h.actor_username ?? 'system'}</span> {describe(h)}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

export default function ComplaintDetail() {
  const { id } = useParams();
  const { data, isLoading, error } = useComplaint(id);

  if (isLoading) return <p className="text-sm text-muted">Loading…</p>;
  if (error || !data) return <p className="text-sm">{errorMessage(error, 'Complaint not found.')}</p>;

  const pending = data.analysis_status !== 'completed';
  const p = data.prediction;

  return (
    <div>
      <Link to="/" className="text-sm text-muted hover:text-ink">← Inbox</Link>

      <div className="mt-4 grid grid-cols-1 gap-10 lg:grid-cols-2">
        <div className="space-y-8">
          <div>
            <h2 className="mb-3 text-sm font-medium text-muted">Complaint</h2>
            <p className="border border-rule bg-white p-4 leading-relaxed">{data.raw_text}</p>
            <dl className="mt-4 space-y-1 font-mono text-xs text-muted">
              <div>customer: {data.customer_ref ?? '—'}</div>
              <div>channel: {data.channel}</div>
              <div>submitted: {formatDateTime(data.submitted_at)}</div>
              {data.resolved_at && <div>resolved: {formatDateTime(data.resolved_at)}</div>}
              {data.duplicate_of && (
                <div>
                  duplicate of:{' '}
                  <Link to={`/complaints/${data.duplicate_of}`} className="underline">
                    {data.duplicate_of}
                  </Link>
                </div>
              )}
            </dl>
          </div>

          <div className="flex flex-wrap gap-10 border-t border-rule pt-6">
            <StatusControl complaint={data} />
            <AssigneeControl complaint={data} />
          </div>

          <History id={id} />
        </div>

        <div className="space-y-6">
          {pending ? (
            <p className="text-sm text-muted">Analysis in progress. This view updates itself.</p>
          ) : (
            <>
              <div className="flex items-start gap-8">
                <CategoryControl complaint={data} />
                <div>
                  <h3 className="mb-1 text-sm font-medium text-muted">Priority</h3>
                  <PriorityBadge bucket={p.priority_bucket} />
                  <p className="mt-2 font-mono text-xs text-muted">score {p.priority_score}</p>
                </div>
                <div>
                  <h3 className="mb-1 text-sm font-medium text-muted">Sentiment</h3>
                  <p>{humanize(p.sentiment_label)}</p>
                  <p className="mt-1 font-mono text-xs text-muted">score {p.sentiment_score}</p>
                </div>
              </div>

              <div>
                <h3 className="mb-2 text-sm font-medium text-muted">How this priority was reached</h3>
                <PriorityBreakdown breakdown={p.priority_breakdown} />
              </div>

              <AIField label="Summary" isLoading={false}>
                <span className="text-muted">Generated content arrives with the LLM stage.</span>
              </AIField>

              <AIField label="Suggested resolution" isLoading={false}>
                <span className="text-muted">Generated content arrives with the LLM stage.</span>
              </AIField>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
