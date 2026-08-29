/**
 * HealthScore — Mission Health Score badge (dark theme).
 *
 * Props:
 *   healthScore {number} — 0–100, from the upload response.
 */
export default function HealthScore({ healthScore }) {
  let colorClasses, ringColor, label;
  if (healthScore >= 80) {
    colorClasses = 'text-emerald-400';
    ringColor    = '#10b981';
    label        = 'Nominal';
  } else if (healthScore >= 50) {
    colorClasses = 'text-amber-400';
    ringColor    = '#f59e0b';
    label        = 'Degraded';
  } else {
    colorClasses = 'text-red-400';
    ringColor    = '#ef4444';
    label        = 'Critical';
  }

  const circumference = 2 * Math.PI * 24;
  const offset = circumference - (healthScore / 100) * circumference;

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 flex items-center gap-3">
      {/* Circular progress */}
      <div className="relative w-14 h-14 shrink-0">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 56 56">
          <circle cx="28" cy="28" r="24" fill="none" stroke="#334155" strokeWidth="4" />
          <circle
            cx="28" cy="28" r="24"
            fill="none"
            stroke={ringColor}
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 0.5s ease' }}
          />
        </svg>
        <span className={`absolute inset-0 flex items-center justify-center text-xs font-bold ${colorClasses}`}>
          {healthScore}
        </span>
      </div>
      <div>
        <p className="text-xs text-slate-500 font-semibold uppercase tracking-wide">Mission Health</p>
        <p className={`text-sm font-bold mt-0.5 ${colorClasses}`}>{label}</p>
      </div>
    </div>
  );
}
