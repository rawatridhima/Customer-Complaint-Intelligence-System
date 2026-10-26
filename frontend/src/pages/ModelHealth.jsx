import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { getModelHealth } from '../api/analytics';
import { errorMessage } from '../api/client';
import RangePicker from '../components/RangePicker';
import StatTile from '../components/StatTile';
import { INK, axisProps, pct, rangeForDays, tooltipProps } from '../lib/charts';
import { humanize } from '../lib/format';

function Section({ title, note, children }) {
  return (
    <section className="border-t border-rule pt-6">
      <div className="mb-4 flex items-baseline justify-between gap-4">
        <h2 className="text-sm font-medium">{title}</h2>
        {note && <span className="text-right text-xs text-muted">{note}</span>}
      </div>
      {children}
    </section>
  );
}

// FR-35: how confident the model was, and how often an agent then corrected it.
function ConfidenceChart({ bands, threshold, correctKey, wrongKey, labels }) {
  const data = bands.map((b) => ({ ...b, band: `${b.from.toFixed(2)}–${b.to.toFixed(2)}` }));
  return (
    <div className="h-60">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid vertical={false} stroke="#efece5" />
          <XAxis dataKey="band" {...axisProps} interval={0} angle={-30} textAnchor="end" height={48} />
          <YAxis allowDecimals={false} {...axisProps} />
          <Tooltip {...tooltipProps} />
          <Legend iconType="square" wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey={correctKey} name={labels[0]} stackId="c" fill={INK} isAnimationActive={false} />
          <Bar dataKey={wrongKey} name={labels[1]} stackId="c" fill="#D55E00" isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
      <p className="mt-1 text-xs text-muted">Predictions below {threshold} are sent to an agent for review (FR-09).</p>
    </div>
  );
}

function ConfusionMatrix({ labels, matrix }) {
  const max = Math.max(...matrix.flat(), 1);
  return (
    <div className="overflow-x-auto">
      <table className="text-xs">
        <thead>
          <tr>
            <th className="p-1 text-left font-normal text-muted">true ↓ / predicted →</th>
            {labels.map((l) => (
              <th key={l} className="w-20 p-1 text-left align-bottom font-normal text-muted">{humanize(l)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={labels[i]}>
              <th className="whitespace-nowrap p-1 pr-3 text-left font-normal text-muted">{humanize(labels[i])}</th>
              {row.map((n, j) => {
                const strength = n / max;
                const diagonal = i === j;
                return (
                  <td
                    key={j}
                    className="p-1 text-right font-mono"
                    style={{
                      background: diagonal ? `rgba(0,114,178,${0.08 + strength * 0.6})` : n ? `rgba(213,94,0,${0.08 + Math.min(1, (n / max) * 6) * 0.5})` : undefined,
                      color: diagonal && strength > 0.6 ? 'white' : undefined,
                    }}
                    title={`${humanize(labels[i])} predicted as ${humanize(labels[j])}: ${n}`}
                  >
                    {n}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-muted">Blue: correct. Orange: mistakes, darker means more often.</p>
    </div>
  );
}

function PerClassTable({ rows }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-rule text-left text-xs text-muted">
          <th className="pb-2 font-medium">Category</th>
          <th className="pb-2 text-right font-medium">Precision</th>
          <th className="pb-2 text-right font-medium">Recall</th>
          <th className="pb-2 text-right font-medium">F1</th>
          <th className="pb-2 text-right font-medium">Test cases</th>
        </tr>
      </thead>
      <tbody className="font-mono text-xs">
        {[...rows].sort((a, b) => b.f1 - a.f1).map((r) => (
          <tr key={r.label} className="border-b border-rule/60">
            <td className="py-1.5 font-sans text-sm">{humanize(r.label)}</td>
            <td className="py-1.5 text-right">{r.precision.toFixed(3)}</td>
            <td className="py-1.5 text-right">{r.recall.toFixed(3)}</td>
            <td className="py-1.5 text-right">{r.f1.toFixed(3)}</td>
            <td className="py-1.5 text-right text-muted">{r.support}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Offline({ offline }) {
  if (!offline) {
    return (
      <p className="text-sm text-muted">
        The model's saved test results were not found. Check that <code className="font-mono">ml/models/distilbert-v1-512/</code>{' '}
        exists, then restart the api container.
      </p>
    );
  }
  const m = offline.metrics;
  const e = offline.evaluation;
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Test macro-F1" value={(e?.macro_f1 ?? m?.test_macro_f1)?.toFixed(3)} />
        <StatTile label="Test accuracy" value={e ? pct(e.accuracy, 1) : '—'} />
        <StatTile label="Max input length" value={m?.max_length ? `${m.max_length} tokens` : '—'} />
        <StatTile label="Model" value={<span className="text-base">{offline.model}</span>} hint={m?.mapping_version ? `label mapping ${m.mapping_version}` : null} />
      </div>
      {e ? (
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
          <div>
            <h3 className="mb-2 text-xs text-muted">Per category (FR-35)</h3>
            <PerClassTable rows={e.per_class} />
          </div>
          <div>
            <h3 className="mb-2 text-xs text-muted">Confusion matrix, {e.n} test complaints</h3>
            <ConfusionMatrix labels={e.labels} matrix={e.confusion_matrix} />
          </div>
          <div className="lg:col-span-2">
            <h3 className="mb-2 text-xs text-muted">Confidence on the test set</h3>
            <ConfidenceChart
              bands={e.confidence_histogram.bins.slice(0, -1).map((from, i) => ({
                from: i === 0 ? 0 : from,
                to: e.confidence_histogram.bins[i + 1],
                correct: e.confidence_histogram.correct[i],
                wrong: e.confidence_histogram.wrong[i],
              }))}
              threshold={0.95}
              correctKey="correct"
              wrongKey="wrong"
              labels={['right', 'wrong']}
            />
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted">
          For per-category scores and the confusion matrix, run once from <code className="font-mono">ml/src</code>:{' '}
          <code className="font-mono">python evaluate_model.py --model-dir ../models/distilbert-v1-512 --data-dir ../data</code>
        </p>
      )}
    </div>
  );
}

export default function ModelHealth() {
  const [range, setRange] = useState(() => rangeForDays(30));
  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: ['model-health', range],
    queryFn: () => getModelHealth(range),
    placeholderData: (prev) => prev,
  });

  const live = data?.live;
  const llm = data?.llm;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-rule pb-4">
        <div>
          <h1 className="text-2xl font-semibold">Model health</h1>
          <p className="mt-1 text-sm text-muted">
            <Link to="/analytics" className="underline">← Analytics</Link>
          </p>
        </div>
        <RangePicker value={range} onChange={setRange} />
      </div>

      {error && <p className="text-sm text-red-700">{errorMessage(error)}</p>}
      {isLoading && <p className="text-sm text-muted">Loading…</p>}

      {data && (
        <div className={`space-y-8 ${isFetching ? 'opacity-60' : ''}`}>
          <Section title="In production" note="complaints submitted in the selected range">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <StatTile
                label={`Below ${data.threshold} confidence`}
                value={pct(live.below_threshold_rate, 1)}
                hint={`${live.below_threshold} of ${live.predictions} sent for review (FR-36)`}
                tone={live.below_threshold_rate > 0.3 ? 'warn' : undefined}
              />
              <StatTile label="Corrected by agents" value={pct(live.override_rate, 1)} hint={`${live.overridden} category corrections`} />
              <StatTile label="Average confidence" value={live.avg_confidence?.toFixed(3)} />
              <StatTile label="Average inference" value={live.avg_inference_ms != null ? `${live.avg_inference_ms} ms` : '—'} hint="per complaint, on CPU" />
            </div>
            {live.predictions > 0 && (
              <div className="mt-6 grid grid-cols-1 gap-8 lg:grid-cols-2">
                <div>
                  <h3 className="mb-2 text-xs text-muted">Confidence of live predictions</h3>
                  <ConfidenceChart bands={live.confidence_histogram.map((b) => ({ ...b, kept: b.count - b.corrected }))} threshold={data.threshold}
                    correctKey="kept" wrongKey="corrected" labels={['kept', 'corrected by an agent']} />
                </div>
                <div>
                  <h3 className="mb-2 text-xs text-muted">Corrections agents made</h3>
                  {live.corrections.length === 0 ? (
                    <p className="text-sm text-muted">No category corrections in this range.</p>
                  ) : (
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-rule text-left text-xs text-muted">
                          <th className="pb-2 font-medium">Model said</th>
                          <th className="pb-2 font-medium">Agent changed to</th>
                          <th className="pb-2 text-right font-medium">Times</th>
                        </tr>
                      </thead>
                      <tbody>
                        {live.corrections.slice(0, 8).map((c) => (
                          <tr key={`${c.predicted}-${c.corrected_to}`} className="border-b border-rule/60">
                            <td className="py-1.5">{humanize(c.predicted)}</td>
                            <td className="py-1.5">{humanize(c.corrected_to)}</td>
                            <td className="py-1.5 text-right font-mono text-xs">{c.count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  <p className="mt-3 text-xs text-muted">
                    Every correction is saved as training data.{' '}
                    <Link to="/settings" className="underline">Export it from Settings</Link>.
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    Model versions: {live.model_versions.map((v) => `${v.version} (${v.count})`).join(', ') || '—'}
                  </p>
                </div>
              </div>
            )}
          </Section>

          <Section title="AI replies" note="LLM stage, same range">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
              <StatTile label="Generated" value={llm.generated} />
              <StatTile label="Template fallback" value={llm.fallback} hint="AI unavailable (FR-25)" tone={llm.fallback > 0 ? 'warn' : undefined} />
              <StatTile label="Reused from cache" value={llm.cached} hint="no LLM call (FR-24)" />
              <StatTile label="Avg. tokens" value={llm.avg_tokens} />
              <StatTile label="Approved" value={llm.approved} hint={`${llm.approved_after_edit} edited first`} />
            </div>
          </Section>

          <Section title="On the held-out test set" note="saved when the model was trained">
            <Offline offline={data.offline} />
          </Section>
        </div>
      )}
    </div>
  );
}
