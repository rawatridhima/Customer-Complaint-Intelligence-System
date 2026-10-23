import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { getOverview } from '../api/analytics';
import { errorMessage } from '../api/client';
import RangePicker from '../components/RangePicker';
import StatTile from '../components/StatTile';
import {
  CATEGORY_COLORS,
  PRIORITY_COLORS,
  SENTIMENT_COLORS,
  axisProps,
  rangeForDays,
  tooltipProps,
} from '../lib/charts';
import { CATEGORIES, humanize } from '../lib/format';

const shortDate = (iso) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, { day: 'numeric', month: 'short', timeZone: 'UTC' });

function Section({ title, note, children }) {
  return (
    <section className="border-t border-rule pt-6">
      <div className="mb-4 flex items-baseline justify-between gap-4">
        <h2 className="text-sm font-medium">{title}</h2>
        {note && <span className="text-xs text-muted">{note}</span>}
      </div>
      {children}
    </section>
  );
}

function EmergingIssues({ issues }) {
  if (issues.length === 0) {
    return (
      <p className="text-sm text-muted">
        No category is unusually busy. A category is flagged when its last 7 days are more than two
        standard deviations above its normal week over the 30 days before.
      </p>
    );
  }
  return (
    <ul className="space-y-2">
      {issues.map((i) => (
        <li key={i.category} role="alert" className="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-l-4 border-amber-500 bg-amber-50 px-4 py-3 text-sm">
          <span className="font-medium">{humanize(i.category)}</span>
          <span>
            {i.last_7_days} complaints in the last 7 days
            {i.ratio ? `, ${i.ratio}× a normal week` : ''}
          </span>
          <span className="font-mono text-xs text-muted">
            normal {i.baseline_mean} ± {i.baseline_sd}, alert above {i.threshold}
          </span>
          <Link to={`/?category=${i.category}&sort=priority`} className="ml-auto text-xs underline">
            Open in inbox
          </Link>
        </li>
      ))}
    </ul>
  );
}

function VolumeChart({ data }) {
  const many = data.length > 45;
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -16 }} barCategoryGap={many ? 1 : 3}>
          <CartesianGrid vertical={false} stroke="#efece5" />
          <XAxis dataKey="date" tickFormatter={shortDate} minTickGap={24} {...axisProps} />
          <YAxis allowDecimals={false} {...axisProps} />
          <Tooltip {...tooltipProps} labelFormatter={shortDate} formatter={(v, name) => [v, humanize(name)]} />
          <Legend formatter={humanize} iconType="square" wrapperStyle={{ fontSize: 12 }} />
          {CATEGORIES.map((c) => (
            <Bar key={c} dataKey={c} stackId="v" fill={CATEGORY_COLORS[c]} isAnimationActive={false} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function Distribution({ counts, colors, order }) {
  const data = order.map((k) => ({ name: k, value: counts[k] ?? 0 }));
  const total = data.reduce((s, d) => s + d.value, 0);
  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 48, bottom: 0, left: 8 }}>
          <XAxis type="number" hide allowDecimals={false} />
          <YAxis type="category" dataKey="name" tickFormatter={humanize} width={72} {...axisProps} />
          <Tooltip {...tooltipProps} formatter={(v) => [`${v} (${total ? Math.round((v / total) * 100) : 0}%)`, 'complaints']} labelFormatter={humanize} />
          <Bar dataKey="value" isAnimationActive={false}
            label={{ position: 'right', fontSize: 11, fill: '#6f6d66', formatter: (v) => (total ? `${Math.round((v / total) * 100)}%` : '') }}>
            {data.map((d) => <Cell key={d.name} fill={colors[d.name]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function Analytics() {
  const [range, setRange] = useState(() => rangeForDays(30));
  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: ['analytics', range],
    queryFn: () => getOverview(range),
    placeholderData: (prev) => prev,
  });

  const k = data?.kpis;
  const empty = k && k.total === 0;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-rule pb-4">
        <div>
          <h1 className="text-2xl font-semibold">Analytics</h1>
          <p className="mt-1 text-sm text-muted">
            Complaints submitted in the selected range. <Link to="/analytics/model" className="underline">Model health →</Link>
          </p>
        </div>
        <RangePicker value={range} onChange={setRange} />
      </div>

      {error && <p className="text-sm text-red-700">{errorMessage(error)}</p>}
      {isLoading && <p className="text-sm text-muted">Loading…</p>}

      {data && (
        <div className={`space-y-8 ${isFetching ? 'opacity-60' : ''}`}>
          {/* FR-31 */}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <StatTile label="Complaints" value={k.total} />
            <StatTile label="Still open" value={k.open} hint={k.total ? `${Math.round((k.open / k.total) * 100)}% of the range` : null} />
            <StatTile label="Avg. time to resolve" value={k.avg_resolution_hours != null ? `${k.avg_resolution_hours} h` : '—'} hint={`${k.resolved} resolved`} />
            <StatTile label="P0" value={k.p0} hint={`${k.p0_open} still open`} tone={k.p0_open > 0 ? 'alert' : undefined} />
            <StatTile label="Escalated" value={k.escalated} />
          </div>

          {empty && (
            <p className="border border-rule p-4 text-sm">
              No complaints in this range. For a demo with three months of history, run{' '}
              <code className="font-mono">make seed-history</code>.
            </p>
          )}

          {/* FR-34 */}
          <Section title="Emerging issues" note="last 7 days vs the 30 days before, whatever the range above">
            <EmergingIssues issues={data.emerging} />
          </Section>

          {/* FR-32 */}
          <Section title="Volume by category" note="per day, UTC">
            <VolumeChart data={data.volume} />
          </Section>

          <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
            {/* FR-33 */}
            <Section title="Sentiment">
              <Distribution counts={data.sentiment} colors={SENTIMENT_COLORS} order={['negative', 'neutral', 'positive']} />
            </Section>
            <Section title="Priority">
              <Distribution counts={data.priority} colors={PRIORITY_COLORS} order={['P0', 'P1', 'P2', 'P3']} />
            </Section>
          </div>
        </div>
      )}
    </div>
  );
}
