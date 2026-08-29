import client from './client';

/**
 * generateInsights — POST /insights
 *
 * Sends the session ID to the backend AI engine and returns the full insights
 * response: { session_id, mission_summary, insights[] }.
 *
 * @param {string} sessionId
 * @returns {Promise<object>}
 */
export async function generateInsights(sessionId) {
  const response = await client.post('/insights', { session_id: sessionId });
  return response.data;
}
