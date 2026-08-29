/**
 * InsightCard — renders a single AI insight alongside its anomaly context (dark theme).
 *
 * Props:
 *   insight  {object} — { anomaly_id, explanation, root_cause_hypothesis,
 *                         recommendation, source_chunks, no_strong_match }
 *   anomaly  {object} — { field, timestamp, severity, detection_detail }
 */
export default function InsightCard({ insight, anomaly }) {
  const severityConfig = {
    high:   { border: 'border-l-red-500',   badge: 'bg-red-900/60 text-red-300 border-red-700/50',   dot: 'bg-red-500' },
    medium: { border: 'border-l-amber-500', badge: 'bg-amber-900/60 text-amber-300 border-amber-700/50', dot: 'bg-amber-500' },
    low:    { border: 'border-l-yellow-600', badge: 'bg-yellow-900/60 text-yellow-300 border-yellow-700/50', dot: 'bg-yellow-600' },
  };
  const sv = severityConfig[anomaly.severity] || severityConfig.low;

  return (
    <div className={`bg-slate-800 border border-slate-700 border-l-4 ${sv.border} rounded-xl p-4 flex flex-col gap-3`}>

      {/* ── Header ───────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <div className={`w-2 h-2 rounded-full shrink-0 ${sv.dot}`} />
          <code className="text-blue-300 font-mono text-sm font-semibold">{anomaly.field}</code>
          <span className="text-slate-500 text-xs">at {anomaly.timestamp}</span>
        </div>
        <span className={`${sv.badge} text-xs font-bold px-2.5 py-1 rounded-full border`}>
          {anomaly.severity.toUpperCase()}
        </span>
      </div>

      {/* ── No-strong-match banner ────────────────────────────────────────── */}
      {insight.no_strong_match && (
        <div className="flex items-center gap-2 bg-amber-950/40 border border-amber-800/50 rounded-lg px-3 py-2">
          <span className="text-amber-400 text-sm">⚠</span>
          <p className="text-amber-300 text-xs">
            No reference documents matched — explanation derived from telemetry data only.
          </p>
        </div>
      )}

      {/* ── Explanation ──────────────────────────────────────────────────── */}
      <p className="text-slate-300 text-sm leading-relaxed">{insight.explanation}</p>

      {/* ── Hypothesis ───────────────────────────────────────────────────── */}
      <div className="flex flex-col gap-1.5">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Hypothesis</span>
        <p className="text-slate-300 text-sm leading-relaxed">{insight.root_cause_hypothesis}</p>
      </div>

      {/* ── Recommended Action ───────────────────────────────────────────── */}
      <div className="flex flex-col gap-1.5">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Recommended Action</span>
        <p className="text-slate-300 text-sm leading-relaxed">{insight.recommendation}</p>
      </div>

      {/* ── Sources ──────────────────────────────────────────────────────── */}
      <details className="border-t border-slate-700 pt-3">
        <summary className="text-xs text-blue-400 font-semibold cursor-pointer hover:text-blue-300 transition-colors">
          Sources ({insight.source_chunks.length})
        </summary>
        <div className="mt-3 flex flex-col gap-2">
          {insight.source_chunks.length === 0 ? (
            <p className="text-xs text-slate-500 italic">
              No reference sources — explanation derived from telemetry data only.
            </p>
          ) : (
            insight.source_chunks.map((chunk, i) => (
              <div key={i} className="bg-slate-900 border border-slate-700 rounded-lg p-3 flex flex-col gap-1.5">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-bold text-slate-300 truncate">{chunk.source_doc}</p>
                  <span className="text-xs text-slate-500 ml-2 shrink-0">
                    {(chunk.similarity_score * 100).toFixed(0)}% match
                  </span>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed line-clamp-4">{chunk.chunk_text}</p>
              </div>
            ))
          )}
        </div>
      </details>
    </div>
  );
}
