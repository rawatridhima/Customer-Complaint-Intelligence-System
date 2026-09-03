import { client } from './client';

export const listComplaints = (params) =>
  client.get('/complaints', { params }).then((r) => r.data);

export const getComplaint = (id) =>
  client.get(`/complaints/${id}`).then((r) => r.data);

export const createComplaint = (payload) =>
  client.post('/complaints', payload).then((r) => r.data);

export const updateStatus = (id, status) =>
  client.patch(`/complaints/${id}`, { status }).then((r) => r.data);
