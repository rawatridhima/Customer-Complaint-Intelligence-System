// FR-08, FR-09: the classifier's confidence against the review threshold.
// needsReview comes from the API, which applies the configured threshold;
// the marker line is only a visual guide.
export const REVIEW_THRESHOLD = 0.95;

export default function ConfidenceBar({ value, needsReview }) {
  if (value == null) return null;
  const pct = Math.round(value * 100);

  return (
    <div className="w-40">
      <div className="relative h-1.5 bg-rule">
        <div
          className={needsReview ? 'h-full bg-amber-500' : 'h-full bg-ink'}
          style={{ width: `${pct}%` }}
        />
        <div
          className="absolute top-0 h-full w-px bg-ink/40"
          style={{ left: `${REVIEW_THRESHOLD * 100}%` }}
          title={`Review threshold ${REVIEW_THRESHOLD}`}
        />
      </div>
      <div className="mt-1 font-mono text-xs text-muted">
        {pct}% {needsReview && <span className="text-amber-700">needs review</span>}
      </div>
    </div>
  );
}
