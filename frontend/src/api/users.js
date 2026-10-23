import { client } from './client';

export const listUsers = () => client.get('/users').then((r) => r.data);
export const createUser = (payload) => client.post('/users', payload).then((r) => r.data);
export const updateUser = (id, payload) => client.patch(`/users/${id}`, payload).then((r) => r.data);
