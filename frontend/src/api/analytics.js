import { client } from './client';

export const getOverview = (range) =>
  client.get('/analytics/overview', { params: range }).then((r) => r.data);

export const getModelHealth = (range) =>
  client.get('/analytics/model-health', { params: range }).then((r) => r.data);

export const getPriorityWeights = () =>
  client.get('/settings/priority-weights').then((r) => r.data);

export const setPriorityWeights = (weights, recalculateOpen) =>
  client
    .put('/settings/priority-weights', { weights, recalculate_open: recalculateOpen })
    .then((r) => r.data);

export const resetPriorityWeights = (recalculateOpen) =>
  client
    .delete('/settings/priority-weights', { params: { recalculate_open: recalculateOpen } })
    .then((r) => r.data);

// The export needs the auth header, so it is fetched as a blob and saved,
// rather than opened as a plain link.
export async function downloadFeedbackCsv(range = {}) {
  const r = await client.get('/feedback/export.csv', { params: range, responseType: 'blob' });
  const url = URL.createObjectURL(r.data);
  const a = document.createElement('a');
  a.href = url;
  a.download = `feedback-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
