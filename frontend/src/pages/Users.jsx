import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createUser, listUsers, updateUser } from '../api/users';
import { errorMessage } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { formatDateTime } from '../lib/format';

const ROLES = ['agent', 'manager', 'admin'];
const EMPTY = { username: '', email: '', password: '', role: 'agent' };

function NewUserForm() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(EMPTY);
  const create = useMutation({
    mutationFn: () => createUser(form),
    onSuccess: () => {
      setForm(EMPTY);
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
  const field = (key, props) => (
    <label className="flex flex-col text-xs text-muted">
      {props.label}
      <input
        {...props}
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        className="mt-1 border border-rule bg-white px-2 py-1 text-sm text-ink outline-none focus:border-ink"
        required
      />
    </label>
  );

  return (
    <form onSubmit={(e) => { e.preventDefault(); create.mutate(); }} className="border border-rule bg-white p-4">
      <h2 className="mb-3 text-sm font-medium">Add a user</h2>
      <div className="flex flex-wrap items-end gap-3">
        {field('username', { label: 'Username', autoComplete: 'off', minLength: 3 })}
        {field('email', { label: 'Email', type: 'email', autoComplete: 'off' })}
        {field('password', { label: 'Password (min 8)', type: 'password', autoComplete: 'new-password', minLength: 8 })}
        <label className="flex flex-col text-xs text-muted">
          Role
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}
            className="mt-1 border border-rule bg-white px-2 py-1 text-sm text-ink">
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </label>
        <button type="submit" disabled={create.isPending} className="bg-ink px-4 py-1.5 text-sm text-paper disabled:opacity-40">
          {create.isPending ? 'Adding…' : 'Add user'}
        </button>
      </div>
      {create.error && <p className="mt-2 text-sm text-red-700">{errorMessage(create.error)}</p>}
      {create.isSuccess && <p className="mt-2 text-sm text-green-800">User added. They can sign in now.</p>}
    </form>
  );
}

// FR-39: user management is for administrators only.
export default function Users() {
  const { user: me } = useAuth();
  const queryClient = useQueryClient();
  const { data, error, isLoading } = useQuery({ queryKey: ['users'], queryFn: listUsers });
  const update = useMutation({
    mutationFn: ({ id, payload }) => updateUser(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });

  const toggleActive = (u) => {
    const verb = u.is_active ? 'Deactivate' : 'Reactivate';
    if (window.confirm(`${verb} ${u.username}?${u.is_active ? ' They will be signed out immediately.' : ''}`)) {
      update.mutate({ id: u.user_id, payload: { is_active: !u.is_active } });
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="border-b border-rule pb-4 text-2xl font-semibold">Users</h1>
      <NewUserForm />
      {error && <p className="text-sm text-red-700">{errorMessage(error)}</p>}
      {isLoading && <p className="text-sm text-muted">Loading…</p>}
      {update.error && <p className="text-sm text-red-700">{errorMessage(update.error)}</p>}
      {data && (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-xs text-muted">
              <th className="pb-2 font-medium">Username</th>
              <th className="pb-2 font-medium">Email</th>
              <th className="pb-2 font-medium">Role</th>
              <th className="pb-2 font-medium">Created</th>
              <th className="pb-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {data.map((u) => {
              const self = u.user_id === me.user_id;
              return (
                <tr key={u.user_id} className={`border-b border-rule/60 ${u.is_active ? '' : 'text-muted'}`}>
                  <td className="py-2">{u.username}{self && <span className="ml-2 font-mono text-xs text-muted">you</span>}</td>
                  <td className="py-2">{u.email}</td>
                  <td className="py-2">
                    <select
                      value={u.role}
                      disabled={self || update.isPending}
                      title={self ? 'You cannot change your own role' : undefined}
                      onChange={(e) => update.mutate({ id: u.user_id, payload: { role: e.target.value } })}
                      className="border border-rule bg-white px-2 py-0.5 text-sm disabled:opacity-60"
                    >
                      {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </td>
                  <td className="py-2 font-mono text-xs text-muted">{formatDateTime(u.created_at)}</td>
                  <td className="py-2">
                    <button onClick={() => toggleActive(u)} disabled={self || update.isPending}
                      className="text-xs underline disabled:no-underline disabled:opacity-50">
                      {u.is_active ? 'active · deactivate' : 'disabled · reactivate'}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
