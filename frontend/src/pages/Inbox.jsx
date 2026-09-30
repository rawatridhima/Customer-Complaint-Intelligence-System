import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import { bulkUpdateStatus, listComplaints } from '../api/complaints';
import { errorMessage } from '../api/client';
import PriorityBadge from '../components/PriorityBadge';
import {
  CATEGORIES,
  PRIORITIES,
  SENTIMENTS,
  STATUSES,
  humanize,
} from '../lib/format';

const PAGE_SIZE = 25;
const FILTER_KEYS = [
  'status', 'category', 'priority', 'sentiment', 'assigned', 'date_from', 'date_to', 'sort',
];

function Select({ label, value, onChange, options, allLabel = 'all' }) {
  return (
    <label className="flex flex-col text-xs text-muted">
      {label}
      <select
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 border border-rule bg-white px-2 py-1 text-sm text-ink"
      >
        {allLabel != null && <option value="">{allLabel}</option>}
        {options.map((o) => {
          const [v, text] = Array.isArray(o) ? o : [o, humanize(o)];
          return (
            <option key={v} value={v}>
              {text}
            </option>
          );
        })}
      </select>
    </label>
  );
}

export default function Inbox() {
  const queryClient = useQueryClient();
  // Filters live in the URL, so a filtered view can be bookmarked or shared
  // and survives a refresh.
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = Object.fromEntries(FILTER_KEYS.map((k) => [k, searchParams.get(k) ?? '']));
  const page = Number(searchParams.get('page') ?? 1);

  const setFilter = (key, value) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    next.delete('page'); // new filter, back to page 1
    setSearchParams(next);
  };
  const setPage = (p) => {
    const next = new URLSearchParams(searchParams);
    next.set('page', String(p));
    setSearchParams(next);
  };
  const hasFilters = FILTER_KEYS.some((k) => k !== 'sort' && filters[k]);

  const { data, isLoading, error } = useQuery({
    queryKey: ['complaints', filters, page],
    queryFn: () => listComplaints({ ...filters, page, size: PAGE_SIZE }),
    refetchInterval: 5000,
  });

  // ---- selection and bulk status (FR-29) ----------------------------------
  const [selected, setSelected] = useState(new Set());
  const [bulkStatus, setBulkStatus] = useState('');
  const [bulkResult, setBulkResult] = useState(null);

  // Clear the selection when the visible list changes filter or page.
  useEffect(() => setSelected(new Set()), [searchParams]);

  const pageIds = useMemo(() => (data?.items ?? []).map((c) => c.complaint_id), [data]);
  const allOnPage = pageIds.length > 0 && pageIds.every((id) => selected.has(id));

  const toggle = (id) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  const toggleAll = () => setSelected(allOnPage ? new Set() : new Set(pageIds));

  const bulk = useMutation({
    mutationFn: () => bulkUpdateStatus([...selected], bulkStatus),
    onSuccess: (result) => {
      setBulkResult(result);
      setSelected(new Set());
      setBulkStatus('');
      queryClient.invalidateQueries({ queryKey: ['complaints'] });
      queryClient.invalidateQueries({ queryKey: ['p0-alert'] });
    },
    onError: (err) => setBulkResult({ error: errorMessage(err) }),
  });

  const applyBulk = () => {
    // NFR-18: confirm before changing many complaints at once.
    const n = selected.size;
    if (window.confirm(`Move ${n} complaint${n === 1 ? '' : 's'} to "${humanize(bulkStatus)}"?`)) {
      bulk.mutate();
    }
  };

  if (error) {
    return (
      <p className="text-sm">
        Could not load complaints. {errorMessage(error, 'Check that the backend container is running.')}
      </p>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-baseline justify-between border-b border-rule pb-3">
        <h1 className="text-2xl font-semibold">Inbox</h1>
        {data && (
          <span className="font-mono text-xs text-muted">
            {data.total} complaint{data.total === 1 ? '' : 's'}
          </span>
        )}
      </div>

      {/* Filters (FR-26) */}
      <div className="mb-6 flex flex-wrap items-end gap-3">
        <Select label="Status" value={filters.status} onChange={(v) => setFilter('status', v)} options={STATUSES} />
        <Select label="Category" value={filters.category} onChange={(v) => setFilter('category', v)} options={CATEGORIES} />
        <Select label="Priority" value={filters.priority} onChange={(v) => setFilter('priority', v)} options={PRIORITIES.map((p) => [p, p])} />
        <Select label="Sentiment" value={filters.sentiment} onChange={(v) => setFilter('sentiment', v)} options={SENTIMENTS} />
        <Select
          label="Assigned"
          value={filters.assigned}
          onChange={(v) => setFilter('assigned', v)}
          options={[['me', 'to me'], ['none', 'unassigned']]}
          allLabel="anyone"
        />
        <label className="flex flex-col text-xs text-muted">
          From
          <input
            type="date"
            value={filters.date_from}
            onChange={(e) => setFilter('date_from', e.target.value)}
            className="mt-1 border border-rule bg-white px-2 py-1 text-sm text-ink"
          />
        </label>
        <label className="flex flex-col text-xs text-muted">
          To
          <input
            type="date"
            value={filters.date_to}
            onChange={(e) => setFilter('date_to', e.target.value)}
            className="mt-1 border border-rule bg-white px-2 py-1 text-sm text-ink"
          />
        </label>
        <Select
          label="Sort"
          value={filters.sort || 'newest'}
          onChange={(v) => setFilter('sort', v === 'newest' ? '' : v)}
          options={[['newest', 'newest first'], ['oldest', 'oldest first'], ['priority', 'highest priority']]}
          allLabel={null}
        />
        {hasFilters && (
          <button onClick={() => setSearchParams({})} className="pb-1 text-sm text-muted underline hover:text-ink">
            Clear filters
          </button>
        )}
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="mb-4 flex items-center gap-3 border border-ink bg-white p-3 text-sm">
          <span className="font-medium">{selected.size} selected</span>
          <select
            value={bulkStatus}
            onChange={(e) => setBulkStatus(e.target.value)}
            className="border border-rule px-2 py-1"
          >
            <option value="">Change status to…</option>
            {STATUSES.filter((s) => s !== 'new').map((s) => (
              <option key={s} value={s}>
                {humanize(s)}
              </option>
            ))}
          </select>
          <button
            onClick={applyBulk}
            disabled={!bulkStatus || bulk.isPending}
            className="bg-ink px-3 py-1 text-paper disabled:opacity-40"
          >
            {bulk.isPending ? 'Applying…' : 'Apply'}
          </button>
          <button onClick={() => setSelected(new Set())} className="ml-auto text-muted hover:text-ink">
            Clear selection
          </button>
        </div>
      )}

      {bulkResult && (
        <div className="mb-4 border border-rule p-3 text-sm" role="status">
          {bulkResult.error ? (
            <span className="text-red-700">{bulkResult.error}</span>
          ) : (
            <>
              <span>Updated {bulkResult.updated.length}.</span>
              {bulkResult.failed.length > 0 && (
                <span className="text-amber-800">
                  {' '}
                  {bulkResult.failed.length} could not be changed: {bulkResult.failed[0].reason}
                  {bulkResult.failed.length > 1 && ' (and others)'}.
                </span>
              )}
            </>
          )}
          <button onClick={() => setBulkResult(null)} className="ml-3 text-muted underline">
            ok
          </button>
        </div>
      )}

      {isLoading && <p className="text-sm text-muted">Loading complaints…</p>}

      {data?.items?.length === 0 && (
        <div className="border border-rule p-8 text-center">
          {hasFilters ? (
            <p>No complaints match these filters.</p>
          ) : (
            <>
              <p className="mb-2">No complaints yet.</p>
              <p className="text-sm text-muted">
                Run <code className="font-mono">make seed</code> to load sample data.
              </p>
            </>
          )}
        </div>
      )}

      {data?.items?.length > 0 && (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-xs text-muted">
                <th className="w-8 pb-2">
                  <input type="checkbox" checked={allOnPage} onChange={toggleAll} aria-label="Select all on this page" />
                </th>
                <th className="pb-2 font-medium">Complaint</th>
                <th className="pb-2 font-medium">Category</th>
                <th className="pb-2 font-medium">Sentiment</th>
                <th className="pb-2 font-medium">Priority</th>
                <th className="pb-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((c) => (
                <tr
                  key={c.complaint_id}
                  className={`border-b border-rule/60 hover:bg-white ${selected.has(c.complaint_id) ? 'bg-white' : ''}`}
                >
                  <td className="py-3">
                    <input
                      type="checkbox"
                      checked={selected.has(c.complaint_id)}
                      onChange={() => toggle(c.complaint_id)}
                      aria-label="Select complaint"
                    />
                  </td>
                  <td className="max-w-md truncate py-3 pr-6">
                    <Link to={`/complaints/${c.complaint_id}`} className="hover:underline">
                      {c.raw_text}
                    </Link>
                  </td>
                  <td className="py-3 pr-6 text-muted">
                    {c.prediction ? humanize(c.prediction.category) : 'analysing…'}
                    {c.prediction?.needs_review && (
                      <span className="ml-2 font-mono text-xs text-amber-700" title="Low confidence, check the category">
                        review
                      </span>
                    )}
                  </td>
                  <td className="py-3 pr-6 text-muted">{humanize(c.prediction?.sentiment_label)}</td>
                  <td className="py-3 pr-6">
                    <PriorityBadge bucket={c.prediction?.priority_bucket} />
                  </td>
                  <td className="py-3 text-muted">{humanize(c.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {data.pages > 1 && (
            <div className="mt-4 flex items-center justify-end gap-3 text-sm">
              <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="text-muted hover:text-ink disabled:opacity-30">
                ← Previous
              </button>
              <span className="font-mono text-xs text-muted">
                page {page} of {data.pages}
              </span>
              <button disabled={page >= data.pages} onClick={() => setPage(page + 1)} className="text-muted hover:text-ink disabled:opacity-30">
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
