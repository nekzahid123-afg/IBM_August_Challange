/**
 * SubsystemTable — dark theme subsystem status table.
 *
 * Props:
 *   rows {object[]} — full telemetry rows from GET /telemetry.
 */
export default function SubsystemTable({ rows }) {
  const counts = {};
  for (const row of rows) {
    const status = row.subsystem_status ?? 'unknown';
    counts[status] = (counts[status] ?? 0) + 1;
  }

  const entries = Object.entries(counts).sort(([a], [b]) => a.localeCompare(b));

  function pillClass(status) {
    switch (status.toLowerCase()) {
      case 'nominal':  return 'bg-emerald-900/60 text-emerald-300 border border-emerald-700/50';
      case 'warning':  return 'bg-amber-900/60  text-amber-300  border border-amber-700/50';
      case 'critical': return 'bg-red-900/60    text-red-300    border border-red-700/50';
      default:         return 'bg-slate-700/60  text-slate-400  border border-slate-600/50';
    }
  }

  return (
    <div>
      <h3 className="text-sm font-semibold text-slate-200 mb-3">Subsystem Status</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700">
            <th className="text-left pb-2 pr-4 text-xs font-semibold text-slate-500 uppercase tracking-wide">Status</th>
            <th className="text-right pb-2 text-xs font-semibold text-slate-500 uppercase tracking-wide">Readings</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([status, count]) => (
            <tr key={status} className="border-b border-slate-800 last:border-0">
              <td className="py-2.5 pr-4">
                <span className={`${pillClass(status)} text-xs font-semibold px-2.5 py-1 rounded-full`}>
                  {status}
                </span>
              </td>
              <td className="py-2.5 text-right text-slate-300 font-semibold tabular-nums">{count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
