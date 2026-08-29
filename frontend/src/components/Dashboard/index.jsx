import { useEffect, useState } from 'react';
import { getTelemetry, getAnomalies } from '../../api/telemetry';
import HealthScore from './HealthScore';
import TelemetryChart from './TelemetryChart';
import SubsystemTable from './SubsystemTable';
import AIInsightsPanel from '../AIInsightsPanel';
import ChatSupport from '../ChatSupport';

/**
 * Numeric telemetry fields to chart — hard-coded from NOMINAL_RANGES keys
 * (canonical source: backend/anomaly/nominal_ranges.py).
 */
const NUMERIC_FIELDS = [
  'battery_voltage',
  'temperature_c',
  'signal_strength_db',
  'solar_panel_efficiency_pct',
  'fuel_level_pct',
  'altitude_km',
  'velocity_kms',
];

/**
 * Dashboard
 *
 * Props:
 *   sessionId    {string} — hex session ID returned by the upload endpoint.
 *   healthScore  {number} — pre-computed by the upload endpoint (0–100).
 *   summaryStats {object} — { row_count, fields, time_range } from upload response.
 *   onReset      {()=>void} — callback to return to the UploadPanel.
 */
export default function Dashboard({ sessionId, healthScore, summaryStats, onReset }) {
  const [rows,            setRows]            = useState([]);
  const [anomalies,       setAnomalies]       = useState([]);
  const [loadingStatus,   setLoadingStatus]   = useState('loading');
  const [anomaliesStatus, setAnomaliesStatus] = useState('loading');
  const [error,           setError]           = useState(null);

  useEffect(() => {
    setLoadingStatus('loading');
    setAnomaliesStatus('loading');

    Promise.all([
      getTelemetry(sessionId),
      getAnomalies(sessionId),
    ])
      .then(([telemetryResult, anomaliesResult]) => {
        setRows(telemetryResult.rows);
        setLoadingStatus('success');
        setAnomalies(anomaliesResult.anomalies);
        setAnomaliesStatus('success');
      })
      .catch((err) => {
        const msg =
          err?.response?.data?.error?.message ||
          err?.message ||
          'Failed to load mission data.';
        setError(msg);
        setLoadingStatus('error');
        setAnomaliesStatus('error');
      });
  }, [sessionId]);

  // ── loading state ──────────────────────────────────────────────────────────

  if (loadingStatus === 'loading') {
    return (
      <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center gap-4">
        <div className="w-10 h-10 border-4 border-slate-600 border-t-blue-400 rounded-full animate-spin" />
        <p className="text-slate-400 text-sm">Loading telemetry data…</p>
      </div>
    );
  }

  if (loadingStatus === 'error') {
    return (
      <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center gap-4 px-4">
        <div className="bg-red-950/50 border border-red-700 rounded-xl px-6 py-4 text-red-300 text-sm max-w-md text-center">
          {error}
        </div>
        <button
          type="button"
          className="px-5 py-2.5 rounded-xl border border-slate-600 text-slate-300 text-sm hover:border-slate-500 transition-colors"
          onClick={onReset}
        >
          ← Try Again
        </button>
      </div>
    );
  }

  // ── group anomalies by field ───────────────────────────────────────────────

  const anomaliesByField = {};
  for (const field of NUMERIC_FIELDS) {
    anomaliesByField[field] = [];
  }
  for (const anomaly of anomalies) {
    if (anomaliesByField[anomaly.field]) {
      anomaliesByField[anomaly.field].push(anomaly);
    }
  }

  const totalAnomalies = anomalies.length;
  const highCount = anomalies.filter(a => a.severity === 'high').length;

  // ── render ─────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      {/* ── Top nav bar ──────────────────────────────────────────────────── */}
      <nav className="sticky top-0 z-40 bg-slate-900/95 backdrop-blur border-b border-slate-800 px-4 md:px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-base">🛰</div>
            <div>
              <h1 className="text-white font-bold text-sm leading-none">OrbitLens AI</h1>
              <p className="text-slate-500 text-xs mt-0.5">Mission Dashboard</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="hidden sm:block text-xs text-slate-600 font-mono bg-slate-800 border border-slate-700 px-2 py-1 rounded">
              {sessionId.slice(0, 12)}…
            </span>
            <button
              type="button"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-700 text-slate-400
                         text-xs font-medium hover:border-slate-600 hover:text-slate-300 transition-colors"
              onClick={onReset}
            >
              ← New Mission
            </button>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 md:px-6 py-6 pb-24">

        {/* ── Stats row ──────────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <HealthScore healthScore={healthScore} />

          <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 flex flex-col gap-1">
            <span className="text-xs text-slate-500 font-semibold uppercase tracking-wide">Readings</span>
            <span className="text-2xl font-bold text-white">{summaryStats.row_count}</span>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 flex flex-col gap-1">
            <span className="text-xs text-slate-500 font-semibold uppercase tracking-wide">Anomalies</span>
            <span className={[
              'text-2xl font-bold',
              anomaliesStatus === 'success'
                ? (highCount > 0 ? 'text-red-400' : totalAnomalies > 0 ? 'text-amber-400' : 'text-emerald-400')
                : 'text-slate-500',
            ].join(' ')}>
              {anomaliesStatus === 'success' ? totalAnomalies : '…'}
            </span>
            {anomaliesStatus === 'success' && highCount > 0 && (
              <span className="text-xs text-red-500">{highCount} high severity</span>
            )}
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 flex flex-col gap-1">
            <span className="text-xs text-slate-500 font-semibold uppercase tracking-wide">Time Range</span>
            <span className="text-sm font-semibold text-white leading-snug">
              {summaryStats.time_range.start.slice(11, 19)}
              <span className="text-slate-500 mx-1">→</span>
              {summaryStats.time_range.end.slice(11, 19)}
            </span>
          </div>
        </div>

        {/* ── Charts grid ────────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 mb-6">
          {NUMERIC_FIELDS.map((field) => (
            <div key={field} className="bg-slate-800 border border-slate-700 rounded-xl p-4">
              <TelemetryChart
                field={field}
                rows={rows}
                anomalies={anomaliesByField[field]}
              />
            </div>
          ))}
        </div>

        {/* ── Bottom row: Subsystem Table ─────────────────────────────────── */}
        <div className="mb-6">
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
            <SubsystemTable rows={rows} />
          </div>
        </div>

        {/* ── AI Insights Panel ───────────────────────────────────────────── */}
        {anomaliesStatus === 'success' && (
          <AIInsightsPanel sessionId={sessionId} anomalies={anomalies} />
        )}
      </div>

      {/* ── Chat Support — always visible ───────────────────────────────── */}
      <ChatSupport sessionId={sessionId} />
    </div>
  );
}
