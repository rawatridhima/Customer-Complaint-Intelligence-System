import { client } from './client';

// Drop empty filters so the URL only carries what is set.
const clean = (params = {}) =>
  Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v != null));

export const listComplaints = (params) =>
  client.get('/complaints', { params: clean(params) }).then((r) => r.data);

export const getComplaint = (id) =>
  client.get(`/complaints/${id}`).then((r) => r.data);

export const createComplaint = (payload) =>
  client.post('/complaints', payload).then((r) => r.data);

export const updateStatus = (id, status) =>
  client.patch(`/complaints/${id}`, { status }).then((r) => r.data);

export const bulkUpdateStatus = (complaintIds, status) =>
  client
    .patch('/complaints/bulk-status', { complaint_ids: complaintIds, status })
    .then((r) => r.data);

export const overrideCategory = (id, category) =>
  client.patch(`/complaints/${id}/category`, { category }).then((r) => r.data);

export const assignComplaint = (id, userId) =>
  client.patch(`/complaints/${id}/assignee`, { user_id: userId }).then((r) => r.data);

export const getHistory = (id) =>
  client.get(`/complaints/${id}/history`).then((r) => r.data);
