const STYLES = {
  P0: { box: 'border-red-700 bg-red-50 text-red-900', mark: '▲▲' },
  P1: { box: 'border-orange-600 bg-orange-50 text-orange-900', mark: '▲' },
  P2: { box: 'border-amber-500 bg-amber-50 text-amber-900', mark: '■' },
  P3: { box: 'border-rule bg-white text-muted', mark: '·' },
};

// NFR-16: priority must never be conveyed by colour alone.
export default function PriorityBadge({ bucket }) {
  if (!bucket) return <span className="text-muted">—</span>;
  const s = STYLES[bucket];
  return (
    <span className={`inline-flex items-center gap-1.5 border px-2 py-0.5 font-mono text-xs ${s.box}`}>
      <span aria-hidden="true">{s.mark}</span>
      {bucket}
    </span>
  );
}
