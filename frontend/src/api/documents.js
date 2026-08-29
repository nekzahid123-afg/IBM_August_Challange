import client from './client';

/**
 * Upload one or more reference documents (PDF, DOCX, TXT, MD) and index them.
 *
 * session_id is optional. When null/undefined the backend auto-creates a
 * document-only session so uploads work without a CSV telemetry session.
 *
 * @param {string|null} sessionId
 * @param {File[]}      files
 * @returns {Promise<object[]>}
 */
export async function uploadDocuments(sessionId, files) {
  const results = [];
  for (const file of files) {
    const form = new FormData();
    form.append('file', file);
    const url = sessionId ? `/documents?session_id=${sessionId}` : '/documents';
    const { data } = await client.post(url, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    results.push({ filename: file.name, ...data });
  }
  return results;
}
