// "credit_report_dispute" -> "credit report dispute"
export const humanize = (value) => (value ? String(value).replaceAll('_', ' ') : '—');

export const CATEGORIES = [
  'credit_report_dispute',
  'report_misuse',
  'debt_collection',
  'cards_and_accounts',
  'mortgage',
  'consumer_loans',
];
export const STATUSES = ['new', 'in_review', 'awaiting_customer', 'escalated', 'resolved'];
export const PRIORITIES = ['P0', 'P1', 'P2', 'P3'];
export const SENTIMENTS = ['negative', 'neutral', 'positive'];

export const formatDateTime = (iso) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '—';
