import { rangeForDays } from '../lib/charts';

const PRESETS = [7, 30, 90];

// Preset buttons plus custom from/to dates. value = { date_from, date_to }.
export default function RangePicker({ value, onChange }) {
  const active = PRESETS.find((d) => {
    const r = rangeForDays(d);
    return r.date_from === value.date_from && r.date_to === value.date_to;
  });
  return (
    <div className="flex flex-wrap items-end gap-3 text-sm">
      <div className="flex gap-1">
        {PRESETS.map((d) => (
          <button
            key={d}
            onClick={() => onChange(rangeForDays(d))}
            className={`px-3 py-1 ${active === d ? 'bg-ink text-paper' : 'text-muted hover:text-ink'}`}
          >
            {d} days
          </button>
        ))}
      </div>
      <label className="flex flex-col text-xs text-muted">
        From
        <input type="date" value={value.date_from} max={value.date_to}
          onChange={(e) => e.target.value && onChange({ ...value, date_from: e.target.value })}
          className="mt-1 border border-rule bg-white px-2 py-1 text-sm text-ink" />
      </label>
      <label className="flex flex-col text-xs text-muted">
        To
        <input type="date" value={value.date_to} min={value.date_from}
          onChange={(e) => e.target.value && onChange({ ...value, date_to: e.target.value })}
          className="mt-1 border border-rule bg-white px-2 py-1 text-sm text-ink" />
      </label>
    </div>
  );
}
