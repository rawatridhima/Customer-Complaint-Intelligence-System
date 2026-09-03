// FR-08, FR-09: shows the classifier's confidence against the review threshold.
export default function ConfidenceBar({ value, threshold = 0.75 }) {
  if (value == null) return null;
  const pct = Math.round(value * 100);
  const below = value < threshold;

  return (
    <div className="w-40">
      <div className="relative h-1.5 bg-rule">
        <div
          className={below ? 'h-full bg-amber-500' : 'h-full bg-ink'}
          style={{ width: `${pct}%` }}
        />
        <div
          className="absolute top-0 h-full w-px bg-ink/40"
          style={{ left: `${threshold * 100}%` }}
          title={`Review threshold ${threshold}`}
        />
      </div>
      <div className="mt-1 font-mono text-xs text-muted">
        {pct}% {below && <span className="text-amber-700">needs review</span>}
      </div>
    </div>
  );
}
