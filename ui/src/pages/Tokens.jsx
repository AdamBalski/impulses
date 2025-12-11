import { useState, useEffect } from 'react';
import { api } from '../api';

export default function Tokens() {
  const [tokens, setTokens] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [newTokenName, setNewTokenName] = useState('');
  const [newTokenCapability, setNewTokenCapability] = useState('SUPER');
  const [createdToken, setCreatedToken] = useState(null);
  const [storedToken, setStoredToken] = useState(localStorage.getItem('impulses_token'));

  useEffect(() => {
    loadTokens();
  }, []);

  async function loadTokens() {
    try {
      setLoading(true);
      const data = await api.listTokens();
      setTokens(data || []);
      setError('');
    } catch (err) {
      setError(err.message || 'Failed to load tokens');
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateToken(e) {
    e.preventDefault();
    if (!newTokenName) return;

    try {
      setCreating(true);
      const token = await api.createToken(newTokenName, newTokenCapability);
      setCreatedToken(token);
      setNewTokenName('');
      loadTokens();
    } catch (err) {
      setError(err.message || 'Failed to create token');
    } finally {
      setCreating(false);
    }
  }

  async function handleDeleteToken(tokenId) {
    if (!confirm('Delete this token? This cannot be undone.')) {
      return;
    }

    try {
      await api.deleteToken(tokenId);
      loadTokens();
    } catch (err) {
      setError(err.message || 'Failed to delete token');
    }
  }

  function saveTokenToLocalStorage(token) {
    localStorage.setItem('impulses_token', token);
    setStoredToken(token);
    setCreatedToken(null);
  }

  function clearStoredToken() {
    if (!confirm('Clear stored token? You will need to create a new one.')) {
      return;
    }
    localStorage.removeItem('impulses_token');
    setStoredToken(null);
  }

  if (loading) {
    return <div className="loading">Loading tokens...</div>;
  }

  return (
    <div>
      <h2>API Tokens</h2>
      <p>Create tokens to authenticate with the Impulses SDK and API.</p>
      <p><strong>For Web UI:</strong> Create a SUPER token and click "Save for Metrics Use" to enable the Metrics page.</p>

      {error && <div className="error">{error}</div>}

      {storedToken && (
        <div className="success">
          <h3>Active Token for Metrics</h3>
          <p>A token is currently stored and will be used for metrics operations.</p>
          <p><code>{storedToken.substring(0, 20)}...</code></p>
          <div className="button-group">
            <button onClick={() => api.startGoogleOAuthFlow(storedToken)}>
              Connect Google Calendar
            </button>
            <button onClick={clearStoredToken}>Clear Stored Token</button>
          </div>
        </div>
      )}

      {createdToken && (
        <div className="token-secret">
          <h3>Token Created!</h3>
          <p><strong>Save this token now. You won't see it again.</strong></p>
          <p>Name: <strong>{createdToken.name}</strong></p>
          <p>Capability: <strong>{createdToken.capability}</strong></p>
          <p>Token:</p>
          <pre style={{ background: '#fff', padding: '1em', border: '1px solid #000' }}>
            {createdToken.token_plaintext}
          </pre>
          <div className="button-group">
            {createdToken.capability === 'SUPER' && (
              <button onClick={() => saveTokenToLocalStorage(createdToken.token_plaintext)}>
                Save for Metrics Use
              </button>
            )}
            <button onClick={() => setCreatedToken(null)}>Close</button>
          </div>
        </div>
      )}

      <div className="card">
        <h3>Create New Token</h3>
        <form onSubmit={handleCreateToken}>
          <label>
            Token Name:
            <input
              type="text"
              value={newTokenName}
              onChange={(e) => setNewTokenName(e.target.value)}
              placeholder="e.g., my-laptop, production-server"
              required
            />
          </label>

          <label>
            Capability:
            <select
              value={newTokenCapability}
              onChange={(e) => setNewTokenCapability(e.target.value)}
            >
              <option value="API">API - Read access</option>
              <option value="INGEST">INGEST - Write access</option>
              <option value="SUPER">SUPER - Full access</option>
            </select>
          </label>

          <button type="submit" disabled={creating}>
            {creating ? 'Creating...' : 'Create Token'}
          </button>
        </form>
      </div>

      <h3>Your Tokens ({tokens.length})</h3>
      {tokens.length === 0 ? (
        <p>No tokens yet. Create one above.</p>
      ) : (
        <div>
          {tokens.map((token) => (
            <div key={token.id} className="token-item">
              <div>
                <strong>{token.name}</strong>
                <br />
                <small>
                  Capability: {token.capability} | 
                  Expires: {new Date(token.expires_at * 1000).toLocaleDateString()} |
                  Created: {token.created_at ? new Date(token.created_at * 1000).toLocaleDateString() : 'N/A'}
                </small>
              </div>
              <button onClick={() => handleDeleteToken(token.id)}>Delete</button>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <h3>Token Capabilities</h3>
        <ul>
          <li><strong>API</strong> - Read-only access. Can list and fetch metrics.</li>
          <li><strong>INGEST</strong> - Write access. Can add and delete datapoints.</li>
          <li><strong>SUPER</strong> - Full access. All API and INGEST permissions.</li>
        </ul>
      </div>
    </div>
  );
}
