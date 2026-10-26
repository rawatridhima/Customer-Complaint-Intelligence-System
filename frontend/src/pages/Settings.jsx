import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  downloadFeedbackCsv,
  getPriorityWeights,
  resetPriorityWeights,
  setPriorityWeights,
} from '../api/analytics';
import { errorMessage } from '../api/client';
import { formatDateTime } from '../lib/format';

const FACTORS = [
  ['sentiment', 'Sentiment negativity', 'How negative the complaint reads.'],
  ['category', 'Category severity', 'How serious its category is (fraud and mortgage highest).'],
  ['urgency', 'Urgency keywords', 'Words like "fraud", "lawyer", "immediately".'],
  ['repeat', 'Repeat complaint', 'The customer has complained before.'],
];

// FR-17: managers change the priority formula without a code change.
function PriorityWeights() {
  const queryClient = useQueryClient();
  const { data, error } = useQuery({ queryKey: ['priority-weights'], queryFn: getPriorityWeights });
  const [draft, setDraft] = useState(null);
  const [recalculate, setRecalculate] = useState(true);
  const [lastEdited, setLastEdited] = useState(null);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    if (data) setDraft(data.weights);
  }, [data]);

  const onDone = (result) => {
    queryClient.setQueryData(['priority-weights'], result);
    queryClient.invalidateQueries({ queryKey: ['complaints'] });
    queryClient.invalidateQueries({ queryKey: ['p0-alert'] });
    setMessage(result.rescored ? `Saved. ${result.rescored} open complaints were re-scored.` : 'Saved. New complaints will use these weights.');
  };
  const save = useMutation({ mutationFn: () => setPriorityWeights(draft, recalculate), onSuccess: onDone });
  const reset = useMutation({ mutationFn: () => resetPriorityWeights(recalculate), onSuccess: onDone });

  if (error) return <p className="text-sm text-red-700">{errorMessage(error)}</p>;
  if (!data || !draft) return <p className="text-sm text-muted">Loading…</p>;

  const total = FACTORS.reduce((s, [k]) => s + (Number(draft[k]) || 0), 0);
  const sumsToOne = Math.abs(total - 1) < 0.001;
  const changed = FACTORS.some(([k]) => Number(draft[k]) !== data.weights[k]);
  const busy = save.isPending || reset.isPending;

  // Keep the factor the manager just changed, and scale the other three so
  // the total is exactly 1 (rounded to 2 decimals, any rounding left over goes
  // on the largest of them).
  const balance = () => {
    const fixed = lastEdited ?? FACTORS[0][0];
    const fixedValue = Math.min(1, Math.max(0, Number(draft[fixed]) || 0));
    const others = FACTORS.map(([k]) => k).filter((k) => k !== fixed);
    const othersTotal = others.reduce((sum, k) => sum + (Number(draft[k]) || 0), 0);
    const room = 1 - fixedValue;
    const next = { ...draft, [fixed]: fixedValue };
    others.forEach((k) => {
      const share = othersTotal > 0 ? (Number(draft[k]) || 0) / othersTotal : 1 / others.length;
      next[k] = Math.round(share * room * 100) / 100;
    });
    const drift = Math.round((1 - FACTORS.reduce((sum, [k]) => sum + next[k], 0)) * 100) / 100;
    if (drift !== 0) {
      const largest = others.reduce((a, b) => (next[a] >= next[b] ? a : b));
      next[largest] = Math.round((next[largest] + drift) * 100) / 100;
    }
    setDraft(next);
  };

  const onSave = () => {
    if (recalculate && !window.confirm('Save the new weights and re-score every open complaint?')) return;
    setMessage(null);
    save.mutate();
  };

  return (
    <section>
      <h2 className="mb-1 text-lg font-semibold">Priority weights</h2>
      <p className="mb-4 text-sm text-muted">
        A complaint's priority score is the weighted sum of four factors. The weights must add up to 1.
        {data.is_custom
          ? ` Last changed by ${data.updated_by ?? 'unknown'} on ${formatDateTime(data.updated_at)}.`
          : ' These are the defaults from the server configuration.'}
      </p>

      <table className="w-full max-w-2xl text-sm">
        <tbody>
          {FACTORS.map(([key, label, help]) => (
            <tr key={key} className="border-b border-rule/60">
              <td className="py-3 pr-4">
                <div>{label}</div>
                <div className="text-xs text-muted">{help}</div>
              </td>
              <td className="w-48 py-3">
                <input
                  type="range" min="0" max="1" step="0.05"
                  value={draft[key]}
                  onChange={(e) => { setLastEdited(key); setDraft({ ...draft, [key]: Number(e.target.value) }); }}
                  className="w-full accent-ink"
                  aria-label={label}
                />
              </td>
              <td className="w-24 py-3 pl-3">
                <input
                  type="number" min="0" max="1" step="0.05"
                  value={draft[key]}
                  onChange={(e) => { setLastEdited(key); setDraft({ ...draft, [key]: e.target.value === '' ? 0 : Number(e.target.value) }); }}
                  className="w-20 border border-rule bg-white px-2 py-1 text-right font-mono text-sm"
                />
              </td>
              <td className="w-16 py-3 text-right font-mono text-xs text-muted">
                default {data.defaults[key]}
              </td>
            </tr>
          ))}
          <tr>
            <td className="py-3 text-sm font-medium">Total</td>
            <td />
            <td className={`py-3 pl-3 font-mono text-sm ${sumsToOne ? '' : 'text-red-700'}`}>{total.toFixed(2)}</td>
            <td className="py-3 text-right text-xs">
              {!sumsToOne && (
                <button onClick={balance} className="whitespace-nowrap text-ink underline">
                  Make them add up to 1
                </button>
              )}
            </td>
          </tr>
        </tbody>
      </table>

      <label className="mt-4 flex items-center gap-2 text-sm">
        <input type="checkbox" checked={recalculate} onChange={(e) => setRecalculate(e.target.checked)} />
        Also re-score complaints that are still open (resolved ones keep their score)
      </label>

      <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
        <button onClick={onSave} disabled={busy || !sumsToOne || !changed}
          className="bg-ink px-4 py-1.5 text-paper disabled:opacity-40">
          {save.isPending ? 'Saving…' : 'Save weights'}
        </button>
        <button onClick={() => setDraft(data.weights)} disabled={busy || !changed}
          className="border border-rule px-3 py-1.5 hover:border-ink disabled:opacity-40">
          Undo changes
        </button>
        {data.is_custom && (
          <button onClick={() => { setMessage(null); reset.mutate(); }} disabled={busy}
            className="ml-auto text-muted underline hover:text-ink disabled:opacity-40">
            {reset.isPending ? 'Resetting…' : 'Reset to defaults'}
          </button>
        )}
      </div>
      {!sumsToOne && (
        <p className="mt-3 text-sm text-red-700">
          The weights add up to {total.toFixed(2)}; they must add up to exactly 1.00 before you can save.
          Adjust them, or use <span className="underline">Make them add up to 1</span>
          {lastEdited ? `, which keeps ${FACTORS.find(([k]) => k === lastEdited)[1].toLowerCase()} at ${draft[lastEdited]}` : ''}.
        </p>
      )}
      {message && <p role="status" className="mt-3 text-sm text-green-800">{message}</p>}
      {(save.error || reset.error) && <p className="mt-3 text-sm text-red-700">{errorMessage(save.error || reset.error)}</p>}
    </section>
  );
}

// FR-42: the corrections agents made, as a CSV for retraining.
function FeedbackExport() {
  const [state, setState] = useState(null);
  const download = async () => {
    setState('working');
    try {
      await downloadFeedbackCsv();
      setState(null);
    } catch (err) {
      setState(errorMessage(err, 'Download failed.'));
    }
  };
  return (
    <section>
      <h2 className="mb-1 text-lg font-semibold">Training feedback</h2>
      <p className="mb-4 max-w-2xl text-sm text-muted">
        Every category an agent corrected, with the redacted complaint text, what the model predicted and the
        corrected label. Use it to retrain the classifier. Contains no customer emails, phone or account numbers.
      </p>
      <button onClick={download} disabled={state === 'working'}
        className="border border-ink px-4 py-1.5 text-sm hover:bg-ink hover:text-paper disabled:opacity-40">
        {state === 'working' ? 'Preparing…' : 'Download feedback.csv'}
      </button>
      {state && state !== 'working' && <p className="mt-2 text-sm text-red-700">{state}</p>}
    </section>
  );
}

export default function Settings() {
  return (
    <div className="space-y-12">
      <h1 className="border-b border-rule pb-4 text-2xl font-semibold">Settings</h1>
      <PriorityWeights />
      <FeedbackExport />
    </div>
  );
}
