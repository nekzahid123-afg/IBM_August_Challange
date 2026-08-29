import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceDot,
  Label,
  ResponsiveContainer,
} from 'recharts';

/**
 * Severity → hex fill color (canonical — must match orbitlens-plan.md color table).
 *   "high"   → #ef4444  (red)
 *   "medium" → #f59e0b  (amber)
 *   "low"    → #eab308  (yellow)
 */
const SEVERITY_COLORS = {
  high:   '#ef4444',
  medium: '#f59e0b',
  low:    '#eab308',
};

/**
 * Recharts XAxis + ReferenceDot timestamp alignment decision
 * ──────────────────────────────────────────────────────────
 * Recharts LineChart uses the `x` value of each data point as a string key for
 * categorical XAxis ticks. ReferenceDot.x must be the EXACT same string that
 * appears in the data array to position correctly on the line.
 *
 * Since the backend returns ISO 8601 strings ("YYYY-MM-DDTHH:MM:SSZ") for both
 * telemetry rows and anomaly timestamps, using those strings directly for both
 * XAxis dataKey and ReferenceDot x works without any epoch conversion — as long
 * as the XAxis type is "category" (the default for string values in Recharts).
 *
 * If Recharts fails to align ReferenceDots (requires a numeric scale), convert
 * with: toEpochMs(isoStr) = new Date(isoStr).getTime()
 * and apply to both rows and anomaly x values. For now, the string approach is
 * used and confirmed to work with Recharts 3.x categorical XAxis.
 */

/**
 * CustomTooltip — shown on hover over a chart data point.
 * Looks up whether the hovered timestamp is an anomaly and, if so, renders
 * the severity and detection_detail alongside the raw value.
 */
function CustomTooltip({ active, payload, anomalyByTs, field }) {
  if (!active || !payload?.length) return null;

  const point   = payload[0];
  const ts      = point?.payload?.timestamp;
  const value   = point?.value;
  const anomaly = anomalyByTs[ts];

  return (
    <div style={{
      background:   '#1e293b',
      border:       '1px solid #334155',
      borderRadius: '10px',
      padding:      '10px 14px',
      fontSize:     '12px',
      fontFamily:   '-apple-system, "Segoe UI", system-ui, sans-serif',
      maxWidth:     '260px',
      boxShadow:    '0 4px 16px rgba(0,0,0,0.4)',
    }}>
      <p style={{ margin: '0 0 4px', color: '#64748b' }}>{ts}</p>
      <p style={{ margin: '0 0 4px', color: '#f1f5f9', fontWeight: 600 }}>
        {field.replace(/_/g, ' ')}: {typeof value === 'number' ? value.toFixed(3) : value}
      </p>
      {anomaly && (
        <>
          <p style={{ margin: '4px 0 2px', color: SEVERITY_COLORS[anomaly.severity] ?? '#94a3b8', fontWeight: 700 }}>
            ⚠ {anomaly.severity.toUpperCase()} anomaly
          </p>
          <p style={{ margin: 0, color: '#94a3b8', lineHeight: 1.5, fontSize: '11px' }}>
            {anomaly.detection_detail}
          </p>
        </>
      )}
    </div>
  );
}

/**
 * TelemetryChart — single Recharts LineChart for one telemetry field.
 *
 * Props:
 *   field     {string}   — telemetry column name, e.g. "battery_voltage"
 *   rows      {object[]} — full telemetry rows from GET /telemetry
 *   anomalies {object[]} — anomalies already filtered to this field
 */
export default function TelemetryChart({ field, rows, anomalies }) {
  // Build O(1) anomaly lookup by timestamp for the tooltip closure.
  const anomalyByTs = {};
  for (const a of anomalies) {
    anomalyByTs[a.timestamp] = a;
  }

  // Tick formatter: show HH:MM only to keep x-axis readable.
  // The full ISO string is still used as the data key for ReferenceDot alignment.
  function formatTick(isoStr) {
    if (!isoStr) return '';
    // "2024-01-01T02:30:00Z" → "02:30"
    const timePart = isoStr.slice(11, 16);
    return timePart;
  }

  // Only show a subset of ticks to prevent overcrowding (every ~50th row for 500 rows).
  const tickInterval = Math.max(1, Math.floor(rows.length / 10)) - 1;

  return (
    <div>
      <h4 className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">
        {field.replace(/_/g, ' ')}
      </h4>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
          <XAxis
            dataKey="timestamp"
            tickFormatter={formatTick}
            interval={tickInterval}
            tick={{ fontSize: 10, fill: '#475569' }}
            tickLine={false}
            axisLine={{ stroke: '#334155' }}
          />
          <YAxis
            tick={{ fontSize: 10, fill: '#475569' }}
            tickLine={false}
            axisLine={false}
            width={52}
          />
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
          <Tooltip
            content={
              <CustomTooltip anomalyByTs={anomalyByTs} field={field} />
            }
          />
          <Line
            type="monotone"
            dataKey={field}
            dot={false}
            stroke="#60a5fa"
            strokeWidth={1.5}
            isAnimationActive={false}
          />
          {anomalies.map((anomaly) => (
            <ReferenceDot
              key={anomaly.id}
              x={anomaly.timestamp}
              y={anomaly.value}
              r={5}
              fill={SEVERITY_COLORS[anomaly.severity] ?? '#64748b'}
              stroke="#0f172a"
              strokeWidth={1.5}
            >
              {/* Label provides text fallback — not relying on color alone */}
              <Label
                value={anomaly.severity[0].toUpperCase()}
                position="top"
                style={{ fontSize: 9, fill: SEVERITY_COLORS[anomaly.severity] ?? '#94a3b8', fontWeight: 700 }}
              />
            </ReferenceDot>
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
