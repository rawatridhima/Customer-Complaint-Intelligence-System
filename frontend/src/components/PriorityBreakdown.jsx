// FR-16: shows each factor's contribution to the final priority score.
export default function PriorityBreakdown({ breakdown }) {
  if (!breakdown) return null;
  const rows = Object.entries(breakdown);
  const max = Math.max(...rows.map(([, f]) => f.contribution), 0.01);

  return (
    <table className="w-full text-sm">
      <tbody>
        {rows.map(([name, f]) => (
          <tr key={name} className="border-b border-rule/60">
            <td className="py-1.5 pr-4 text-muted">{name.replace(/_/g, ' ')}</td>
            <td className="w-32 py-1.5">
              <div className="h-2 bg-rule">
                <div className="h-full bg-ink" style={{ width: `${(f.contribution / max) * 100}%` }} />
              </div>
            </td>
            <td className="w-24 py-1.5 text-right font-mono text-xs">
              {f.raw} × {f.weight}
            </td>
            <td className="w-16 py-1.5 text-right font-mono text-xs">{f.contribution}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
