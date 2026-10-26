import { client } from './client';

const base = (id) => `/complaints/${id}/generated-content`;

// Resolves to null while the worker has not produced content yet (404).
export const getGeneratedContent = (id) =>
  client
    .get(base(id))
    .then((r) => r.data)
    .catch((err) => {
      if (err.response?.status === 404) return null;
      throw err;
    });

export const generateContent = (id, tone) =>
  client.post(base(id), tone ? { tone } : null).then((r) => r.data);

export const saveResponseEdit = (id, text) =>
  client.patch(base(id), { final_response: text }).then((r) => r.data);

export const approveResponse = (id, text) =>
  client.post(`${base(id)}/approve`, { final_response: text }).then((r) => r.data);
