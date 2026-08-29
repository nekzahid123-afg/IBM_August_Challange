import client from './client';

/**
 * Send a chat message to the OrbitLens AI backend.
 *
 * @param {string|null} sessionId  — active telemetry session id (may be null before upload)
 * @param {string}      message    — the user's question
 * @returns {Promise<{ session_id: string|null, answer: string, source_chunks: object[] }>}
 */
export async function sendChatMessage(sessionId, message) {
  const { data } = await client.post('/chat', {
    session_id: sessionId ?? null,
    message,
  });
  return data;
}
