import client from './client';

/**
 * Upload a user-supplied CSV file.
 * @param {File} file
 * @returns {Promise<object>} Canonical API Contract response shape.
 */
export async function uploadCSV(file) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await client.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

/**
 * Load the bundled sample mission through the same pipeline as uploadCSV.
 * @returns {Promise<object>} Canonical API Contract response shape.
 */
export async function loadSample() {
  const { data } = await client.get('/upload/sample');
  return data;
}

/**
 * Fetch all telemetry rows for a session.
 * Returns { session_id, rows: [...] } — one object per CSV row with timestamp
 * as an ISO 8601 string ("YYYY-MM-DDTHH:MM:SSZ").
 *
 * @param {string} sessionId
 * @returns {Promise<{ session_id: string, rows: object[] }>}
 */
export async function getTelemetry(sessionId) {
  const { data } = await client.get('/telemetry', {
    params: { session_id: sessionId },
  });
  return data;
}

/**
 * Fetch detected anomalies for a session.
 * Returns { session_id, anomalies: [...] }.
 *
 * @param {string} sessionId
 * @returns {Promise<{ session_id: string, anomalies: object[] }>}
 */
export async function getAnomalies(sessionId) {
  const { data } = await client.get('/anomalies', {
    params: { session_id: sessionId },
  });
  return data;
}
