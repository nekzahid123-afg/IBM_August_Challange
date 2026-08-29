/**
 * report.js — Mission Report download helper.
 *
 * Uses the anchor-click approach so the browser handles the file download
 * directly without popup-blocker interference.
 */

export function downloadReport(sessionId, format = "markdown") {
  const a = document.createElement("a");
  // Use '/api/report' so the Vite dev-server proxy forwards to http://localhost:8000/report.
  // This avoids any dependency on VITE_API_URL being defined at runtime.
  a.href = `/api/report?session_id=${sessionId}&format=${format}`;
  a.download = "";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}
