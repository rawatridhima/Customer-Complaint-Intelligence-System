import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  approveResponse,
  generateContent,
  getGeneratedContent,
  saveResponseEdit,
} from '../api/generatedContent';
import { errorMessage } from '../api/client';
import AIField from './AIField';
import { formatDateTime } from '../lib/format';

const TONES = [
  ['urgent', 'urgent'],
  ['empathetic', 'empathetic'],
  ['professional', 'professional'],
];

// Summary, suggested resolution and the draft reply for one complaint
// (FR-19 to FR-25, FR-27). The worker generates them after analysis; this
// polls until they exist.
export default function ResponsePanel({ complaintId }) {
  const queryClient = useQueryClient();
  const queryKey = ['generated', complaintId];

  const { data: content, isLoading, error } = useQuery({
    queryKey,
    queryFn: () => getGeneratedContent(complaintId),
    refetchInterval: (q) => (q.state.data ? false : 3000),
  });

  const [text, setText] = useState('');
  const [tone, setTone] = useState('');
  const [copied, setCopied] = useState(false);

  // Load the latest text into the editor whenever the content changes.
  useEffect(() => {
    if (content) {
      setText(content.final_response ?? content.draft_response ?? '');
      setTone(content.tone ?? '');
    }
  }, [content?.content_id, content?.draft_response, content?.final_response, content?.tone]);

  const onSaved = (updated) => {
    queryClient.setQueryData(queryKey, updated);
    queryClient.invalidateQueries({ queryKey: ['history', complaintId] });
  };
  const regenerate = useMutation({ mutationFn: () => generateContent(complaintId, tone || null), onSuccess: onSaved });
  const save = useMutation({ mutationFn: () => saveResponseEdit(complaintId, text), onSuccess: onSaved });
  const approve = useMutation({ mutationFn: () => approveResponse(complaintId, text), onSuccess: onSaved });

  if (isLoading || (!content && !error)) {
    return (
      <div className="space-y-6">
        <p className="text-sm text-muted">Writing the summary and a draft reply…</p>
        <AIField label="Summary" isLoading />
        <AIField label="Suggested resolution" isLoading />
      </div>
    );
  }
  if (error) return <p className="text-sm text-red-700">{errorMessage(error)}</p>;

  const approved = Boolean(content.approved_at);
  const saved = content.final_response ?? content.draft_response ?? '';
  const dirty = text !== saved;
  const busy = regenerate.isPending || save.isPending || approve.isPending;
  const actionError = regenerate.error || save.error || approve.error;

  const onRegenerate = () => {
    const edited = content.was_edited || dirty;
    if (edited && !window.confirm('Regenerating replaces the draft and discards your edits. Continue?')) return;
    regenerate.mutate();
  };
  const onApprove = () => {
    // NFR-18 / FR-22: approval is final and is what allows sending.
    if (window.confirm('Approve this reply? It will be locked and ready to send.')) approve.mutate();
  };
  const onCopy = async () => {
    await navigator.clipboard.writeText(content.final_response);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      {content.is_fallback && (
        <div role="alert" className="border-2 border-amber-500 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-medium">Handle this complaint manually.</p>
          <p className="mt-1">
            The AI service could not be used, so the reply below is the standard template.
            {content.fallback_reason && <span className="font-mono text-xs"> ({content.fallback_reason})</span>}
          </p>
          {!approved && (
            <button onClick={onRegenerate} disabled={busy} className="mt-2 underline disabled:opacity-50">
              {regenerate.isPending ? 'Trying again…' : 'Try the AI again'}
            </button>
          )}
        </div>
      )}

      {!content.is_fallback && (
        <>
          <AIField label="Summary" isLoading={regenerate.isPending}>
            {content.summary}
          </AIField>

          <AIField label="Suggested resolution" isLoading={regenerate.isPending}>
            <div className="whitespace-pre-line">{content.suggested_resolution}</div>
            {content.cited_articles.length > 0 ? (
              <p className="mt-2 text-xs text-muted">
                Based on: {content.cited_articles.map((a) => a.title).join('; ')}
              </p>
            ) : (
              <p className="mt-2 text-xs text-amber-800">
                None of the knowledge base articles for this category applied. Check the steps against policy before acting.
              </p>
            )}
          </AIField>
        </>
      )}

      <section className="border-l-2 border-ink/20 pl-4">
        <div className="mb-2 flex items-baseline gap-3">
          <h3 className="text-sm font-medium text-muted">
            Reply to customer <span className="font-mono text-xs">{content.is_fallback ? 'template' : 'generated'}</span>
          </h3>
          {content.was_edited && <span className="font-mono text-xs text-muted">edited</span>}
          {approved && <span className="font-mono text-xs text-green-800">approved</span>}
        </div>

        {approved ? (
          <>
            <div className="whitespace-pre-line border border-rule bg-white p-3 text-sm leading-relaxed">
              {content.final_response}
            </div>
            <div className="mt-2 flex items-center gap-4 text-xs text-muted">
              <span>Approved {formatDateTime(content.approved_at)}. Ready to send.</span>
              <button onClick={onCopy} className="underline hover:text-ink">
                {copied ? 'Copied' : 'Copy reply'}
              </button>
            </div>
          </>
        ) : (
          <>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={10}
              disabled={busy}
              className="w-full border border-rule bg-white p-3 text-sm leading-relaxed outline-none focus:border-ink disabled:opacity-60"
            />
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
              <select
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                disabled={busy}
                className="border border-rule bg-white px-2 py-1"
                aria-label="Tone"
              >
                {TONES.map(([v, label]) => (
                  <option key={v} value={v}>
                    {label} tone
                  </option>
                ))}
              </select>
              <button onClick={onRegenerate} disabled={busy} className="border border-rule px-3 py-1 hover:border-ink disabled:opacity-40">
                {regenerate.isPending ? 'Regenerating…' : 'Regenerate'}
              </button>
              <button onClick={() => save.mutate()} disabled={busy || !dirty || !text.trim()} className="border border-rule px-3 py-1 hover:border-ink disabled:opacity-40">
                {save.isPending ? 'Saving…' : 'Save edit'}
              </button>
              <button onClick={onApprove} disabled={busy || !text.trim()} className="ml-auto bg-ink px-3 py-1 text-paper disabled:opacity-40">
                {approve.isPending ? 'Approving…' : 'Approve reply'}
              </button>
            </div>
            <p className="mt-2 text-xs text-muted">
              Nothing is sent to the customer until you approve it.
              {dirty && ' You have unsaved changes; approving uses the text as it is now.'}
            </p>
          </>
        )}
        {actionError && <p className="mt-2 text-xs text-red-700">{errorMessage(actionError)}</p>}
      </section>

      {content.llm_model && (
        <p className="font-mono text-xs text-muted">
          {content.llm_model} · prompt {content.prompt_version}
          {content.token_count === 0 ? ' · reused from an identical complaint' : content.token_count ? ` · ${content.token_count} tokens` : ''}
        </p>
      )}
    </div>
  );
}
