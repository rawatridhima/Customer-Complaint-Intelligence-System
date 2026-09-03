// NFR-17: every machine-generated field is visibly marked as such.
export default function AIField({ label, isLoading, children }) {
  return (
    <section className="border-l-2 border-ink/20 pl-4">
      <h3 className="mb-1 text-sm font-medium text-muted">
        {label} <span className="font-mono text-xs">generated</span>
      </h3>
      {isLoading ? (
        <div className="space-y-2">
          <div className="h-3 w-full animate-pulse bg-rule" />
          <div className="h-3 w-4/5 animate-pulse bg-rule" />
        </div>
      ) : (
        <div className="text-sm leading-relaxed">{children}</div>
      )}
    </section>
  );
}
