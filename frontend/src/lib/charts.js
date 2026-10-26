// One colour per category, used by every chart so a category always looks
// the same. Okabe-Ito palette: distinguishable with common colour blindness.
// Charts also label series by name (legend, tooltip), so colour is never the
// only cue (NFR-16).
export const CATEGORY_COLORS = {
  credit_report_dispute: '#0072B2',
  report_misuse: '#D55E00',
  debt_collection: '#E69F00',
  cards_and_accounts: '#009E73',
  mortgage: '#CC79A7',
  consumer_loans: '#56B4E9',
};

export const SENTIMENT_COLORS = { negative: '#B4432B', neutral: '#8A8780', positive: '#2E7D4F' };
export const PRIORITY_COLORS = { P0: '#B91C1C', P1: '#EA580C', P2: '#D97706', P3: '#A8A49B' };

export const INK = '#1c1b19';
export const MUTED = '#6f6d66';
export const RULE = '#e0ddd5';

export const axisProps = {
  tick: { fill: MUTED, fontSize: 11, fontFamily: '"IBM Plex Mono", monospace' },
  tickLine: false,
  axisLine: { stroke: RULE },
};

export const tooltipProps = {
  contentStyle: { border: `1px solid ${RULE}`, borderRadius: 0, fontSize: 12 },
  cursor: { fill: 'rgba(28,27,25,0.04)' },
};

export const pct = (v, digits = 0) => (v == null ? '—' : `${(v * 100).toFixed(digits)}%`);

// Date range presets shared by the analytics pages. Dates are UTC days.
const iso = (d) => d.toISOString().slice(0, 10);
export function rangeForDays(days) {
  const to = new Date();
  const from = new Date(to);
  from.setUTCDate(to.getUTCDate() - (days - 1));
  return { date_from: iso(from), date_to: iso(to) };
}
