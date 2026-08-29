import { useState } from 'react';
import UploadPanel from '../components/UploadPanel';
import Dashboard from '../components/Dashboard';

/**
 * Home page.
 *
 * - Renders <UploadPanel> until a CSV is successfully loaded.
 * - On success, stores { sessionId, healthScore, summaryStats } in state and
 *   renders <Dashboard> with those props.
 */
export default function Home() {
  const [session, setSession] = useState(null);

  if (session) {
    return (
      <Dashboard
        sessionId={session.sessionId}
        healthScore={session.healthScore}
        summaryStats={session.summaryStats}
        onReset={() => setSession(null)}
      />
    );
  }

  return <UploadPanel onSuccess={setSession} />;
}
