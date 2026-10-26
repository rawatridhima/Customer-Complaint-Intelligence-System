// A single number with a label, for KPI rows.
export default function StatTile({ label, value, hint, tone }) {
  const color = tone === 'alert' ? 'text-red-800' : tone === 'warn' ? 'text-amber-800' : 'text-ink';
  return (
    <div className="border border-rule bg-white px-4 py-3">
      <div className="text-xs text-muted">{label}</div>
      <div className={`mt-1 font-mono text-2xl ${color}`}>{value ?? '—'}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}
