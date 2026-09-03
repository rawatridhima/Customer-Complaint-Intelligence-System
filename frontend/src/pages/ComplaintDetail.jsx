import { useParams, Link } from 'react-router-dom';
import { useComplaint } from '../hooks/useComplaint';
import PriorityBadge from '../components/PriorityBadge';
import ConfidenceBar from '../components/ConfidenceBar';
import PriorityBreakdown from '../components/PriorityBreakdown';
import AIField from '../components/AIField';

export default function ComplaintDetail() {
  const { id } = useParams();
  const { data, isLoading } = useComplaint(id);

  if (isLoading) return <p className="text-sm text-muted">Loading…</p>;
  if (!data) return <p className="text-sm">Complaint not found.</p>;

  const pending = data.analysis_status !== 'completed';
  const p = data.prediction;

  return (
    <div>
      <Link to="/" className="text-sm text-muted hover:text-ink">← Inbox</Link>

      <div className="mt-4 grid grid-cols-1 gap-10 lg:grid-cols-2">
        <div>
          <h2 className="mb-3 text-sm font-medium text-muted">Complaint</h2>
          <p className="border border-rule bg-white p-4 leading-relaxed">{data.raw_text}</p>
          <dl className="mt-4 space-y-1 font-mono text-xs text-muted">
            <div>customer: {data.customer_ref ?? '—'}</div>
            <div>channel: {data.channel}</div>
            <div>status: {data.status}</div>
            {data.duplicate_of && <div>duplicate of: {data.duplicate_of}</div>}
          </dl>
        </div>

        <div className="space-y-6">
          {pending ? (
            <p className="text-sm text-muted">Analysis in progress. This view updates itself.</p>
          ) : (
            <>
              <div className="flex items-start gap-8">
                <div>
                  <h3 className="mb-1 text-sm font-medium text-muted">Category</h3>
                  <p className="mb-2">{p.category.replace('_', ' ')}</p>
                  <ConfidenceBar value={Number(p.category_confidence)} />
                </div>
                <div>
                  <h3 className="mb-1 text-sm font-medium text-muted">Priority</h3>
                  <PriorityBadge bucket={p.priority_bucket} />
                  <p className="mt-2 font-mono text-xs text-muted">score {p.priority_score}</p>
                </div>
              </div>

              <div>
                <h3 className="mb-2 text-sm font-medium text-muted">How this priority was reached</h3>
                <PriorityBreakdown breakdown={p.priority_breakdown} />
              </div>

              <AIField label="Summary" isLoading={false}>
                Not implemented yet. Person B adds the LLM stage in week 7.
              </AIField>

              <AIField label="Suggested resolution" isLoading={false}>
                Not implemented yet.
              </AIField>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
