import { useState } from 'react';
import { generateInsights } from '../../api/insights';
import { downloadReport } from '../../api/report';
import InsightCard from './InsightCard';

/**
 * AIInsightsPanel — dark theme AI insights section.
 *
 * Props:
 *   sessionId  {string}   — hex session ID.
 *   anomalies  {object[]} — anomaly objects from the anomaly detection response.
 */
export default function AIInsightsPanel({ sessionId, anomalies }) {
  const [status,   setStatus]   = useState('idle');
  const [response, setResponse] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');

  const anomalyById = {};
  for (const anomaly of anomalies) {
    anomalyById[anomaly.id] = anomaly;
  }

  async function handleGenerate() {
    setStatus('loading');
    setErrorMsg('');
    try {
      const data = await generateInsights(sessionId);
      setResponse(data);
      setStatus('success');
    } catch (err) {
      const msg =
        err?.response?.data?.error?.message ||
        err?.message ||
        'Failed to generate insights. Please try again.';
      setErrorMsg(msg);
      setStatus('error');
    }
  }

  const isLoading = status === 'loading';
  const isSuccess = status === 'success';

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-2xl overflow-hidden">
      {/* ── Panel header ────────────────────────────────────────────────── */}
      <div className="px-6 py-4 border-b border-slate-700 bg-slate-800/80">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-white font-bold text-base">🤖 AI Insights</h2>
            <p className="text-slate-500 text-xs mt-1">
              RAG-powered analysis of each anomaly using IBM watsonx + ChromaDB
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              className={[
                'px-5 py-2.5 rounded-xl text-sm font-bold transition-all',
                isLoading
                  ? 'bg-slate-600 text-slate-400 cursor-not-allowed'
                  : 'bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-600/20 hover:shadow-blue-500/30',
              ].join(' ')}
              disabled={isLoading}
              onClick={handleGenerate}
            >
              {isLoading ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-slate-500 border-t-white rounded-full animate-spin" />
                  Generating…
                </span>
              ) : (
                '⚡ Generate AI Insights'
              )}
            </button>

            {isSuccess && (
              <button
                type="button"
                className="px-4 py-2.5 rounded-xl text-sm font-bold bg-violet-700 hover:bg-violet-600 text-white
                           transition-colors shadow-md shadow-violet-700/20"
                onClick={() => downloadReport(sessionId)}
              >
                📄 Export Report
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="p-6 flex flex-col gap-4">
        {/* ── Error state ─────────────────────────────────────────────────── */}
        {status === 'error' && (
          <div className="flex items-start gap-2 bg-red-950/50 border border-red-700 rounded-xl px-4 py-3">
            <span className="text-red-400 text-sm">⚠️</span>
            <p className="text-red-300 text-sm">{errorMsg}</p>
          </div>
        )}

        {/* ── Idle hint ──────────────────────────────────────────────────── */}
        {status === 'idle' && (
          <div className="text-center py-8">
            <div className="text-4xl mb-3">🔬</div>
            <p className="text-slate-400 text-sm">
              Click <strong className="text-white">Generate AI Insights</strong> to run the RAG analysis engine.
            </p>
            <p className="text-slate-600 text-xs mt-1">
              {anomalies.length} anomalies queued for analysis
            </p>
          </div>
        )}

        {/* ── Results ─────────────────────────────────────────────────────── */}
        {isSuccess && response && (
          <>
            {/* Mission Summary */}
            <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wide">Mission Summary</span>
                <span className="flex-1 h-px bg-slate-700" />
              </div>
              <p className="text-slate-300 text-sm leading-relaxed">{response.mission_summary}</p>
            </div>

            {/* Insight Cards */}
            <div className="flex flex-col gap-3">
              {response.insights.map((insight) => {
                const anomaly = anomalyById[insight.anomaly_id];
                if (!anomaly) return null;
                return (
                  <InsightCard
                    key={insight.anomaly_id}
                    insight={insight}
                    anomaly={anomaly}
                  />
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
