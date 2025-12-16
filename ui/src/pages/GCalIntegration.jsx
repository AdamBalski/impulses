import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';

function formatTs(ts) {
  if (ts == null) return 'N/A';
  return new Date(ts * 1000).toLocaleString();
}

export default function GCalIntegration() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        const data = await api.listGoogleOAuthConfigs();
        if (cancelled) return;
        setRows(data || []);
        setError('');
      } catch (err) {
        if (cancelled) return;
        setError(err?.message || 'Failed to load Google Calendar integration status');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const connectedCount = useMemo(() => rows.length, [rows]);

  if (loading) {
    return <div className="loading">Loading Google Calendar integration...</div>;
  }

  return (
    <div>
      <h2>GCal integration</h2>

      {error && <div className="error">{error}</div>}

      {!error && (
        <>
          <p>Connected tokens: <strong>{connectedCount}</strong></p>

          {rows.length === 0 ? (
            <p>No connected tokens found. Go to Tokens and connect Google Calendar for a token.</p>
          ) : (
            <div className="card">
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left', padding: '6px 8px' }}>Token</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px' }}>Connected</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px' }}>Token expiry</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px' }}>Creds updated</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px' }}>Calendar</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px' }}>Last sync</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px' }}>Has sync token</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.token_id}>
                      <td style={{ padding: '6px 8px', borderTop: '1px solid #eee' }}>
                        <div><strong>{r.token_name}</strong></div>
                        <div><small>{r.token_id}</small></div>
                      </td>
                      <td style={{ padding: '6px 8px', borderTop: '1px solid #eee' }}>
                        {r.connected ? 'yes' : 'no'}
                      </td>
                      <td style={{ padding: '6px 8px', borderTop: '1px solid #eee' }}>{formatTs(r.token_expiry)}</td>
                      <td style={{ padding: '6px 8px', borderTop: '1px solid #eee' }}>{formatTs(r.updated_at)}</td>
                      <td style={{ padding: '6px 8px', borderTop: '1px solid #eee' }}>{r.sync?.calendar_id || 'N/A'}</td>
                      <td style={{ padding: '6px 8px', borderTop: '1px solid #eee' }}>{formatTs(r.sync?.last_sync_at)}</td>
                      <td style={{ padding: '6px 8px', borderTop: '1px solid #eee' }}>{r.sync ? (r.sync.has_sync_token ? 'yes' : 'no') : 'N/A'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
