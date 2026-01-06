import { useState, useEffect } from 'react';
import { api } from '../api';

const BLOCKLIST = [
  'impulses_token',
];

const MAX_VALUE_DISPLAY = 200;

function truncateValue(value) {
  if (!value) return '';
  if (value.length <= MAX_VALUE_DISPLAY) return value;
  return value.substring(0, MAX_VALUE_DISPLAY) + '...';
}

function getLocalStorageEntries() {
  const entries = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (BLOCKLIST.includes(key)) continue;
    const value = localStorage.getItem(key);
    entries.push({ key, value });
  }
  return entries.sort((a, b) => a.key.localeCompare(b.key));
}

export default function LocalStorageSync() {
  const [localEntries, setLocalEntries] = useState([]);
  const [dbEntries, setDbEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [syncing, setSyncing] = useState({});
  const [customKey, setCustomKey] = useState('');
  const [customValue, setCustomValue] = useState('');
  const [savingCustom, setSavingCustom] = useState(false);

  useEffect(() => {
    refreshLocalEntries();
    loadDbEntries();
  }, []);

  useEffect(() => {
    if (!notice) return;
    const timeout = setTimeout(() => setNotice(''), 3000);
    return () => clearTimeout(timeout);
  }, [notice]);

  function refreshLocalEntries() {
    setLocalEntries(getLocalStorageEntries());
  }

  async function loadDbEntries() {
    try {
      setLoading(true);
      const data = await api.listLocalStorageEntries();
      setDbEntries(data || []);
      setError('');
    } catch (err) {
      setError(err.message || 'Failed to load database entries');
    } finally {
      setLoading(false);
    }
  }

  async function handleSyncToDb(key) {
    const value = localStorage.getItem(key);
    if (value === null) return;

    setSyncing((prev) => ({ ...prev, [`toDb-${key}`]: true }));
    try {
      await api.upsertLocalStorageEntry(key, value);
      await loadDbEntries();
    } catch (err) {
      setError(err.message || 'Failed to sync to database');
    } finally {
      setSyncing((prev) => ({ ...prev, [`toDb-${key}`]: false }));
    }
  }

  function handleRemoveFromLocal(key) {
    if (!confirm(`Remove "${key}" from local storage?`)) return;
    localStorage.removeItem(key);
    refreshLocalEntries();
  }

  async function handleSyncFromDb(entry) {
    setSyncing((prev) => ({ ...prev, [`fromDb-${entry.id}`]: true }));
    try {
      localStorage.setItem(entry.key, entry.value);
      refreshLocalEntries();
    } catch (err) {
      setError('Failed to save to local storage');
    } finally {
      setSyncing((prev) => ({ ...prev, [`fromDb-${entry.id}`]: false }));
    }
  }

  async function handleRemoveFromDb(entry) {
    if (!confirm(`Remove "${entry.key}" from database?`)) return;

    setSyncing((prev) => ({ ...prev, [`delDb-${entry.id}`]: true }));
    try {
      await api.deleteLocalStorageEntry(entry.id);
      await loadDbEntries();
    } catch (err) {
      setError(err.message || 'Failed to delete from database');
    } finally {
      setSyncing((prev) => ({ ...prev, [`delDb-${entry.id}`]: false }));
    }
  }

  async function handleCopy(value, label) {
    if (typeof value !== 'string') {
      setError('Nothing to copy');
      return;
    }
    try {
      await navigator.clipboard.writeText(value);
      setNotice(`${label} copied to clipboard`);
    } catch (err) {
      setError('Failed to copy to clipboard');
    }
  }

  async function handleCustomSubmit(e) {
    e.preventDefault();
    setError('');
    const trimmedKey = customKey.trim();
    if (!trimmedKey) {
      setError('Key is required');
      return;
    }
    try {
      setSavingCustom(true);
      localStorage.setItem(trimmedKey, customValue);
      refreshLocalEntries();
      setNotice(`Saved ${trimmedKey} in local storage`);
      setCustomKey('');
      setCustomValue('');
    } catch (err) {
      setError('Failed to save value locally');
    } finally {
      setSavingCustom(false);
    }
  }

  return (
    <div>
      <h2>Local Storage Sync</h2>
      <p>Manage and sync your browser's local storage with the database for backup and cross-device access.</p>

      {error && <div className="error">{error}</div>}
      {notice && <div className="success">{notice}</div>}

      <div className="card">
        <h3>Set Custom Key/Value</h3>
        <form onSubmit={handleCustomSubmit}>
          <label>
            Key
            <input
              type="text"
              value={customKey}
              onChange={(e) => setCustomKey(e.target.value)}
              placeholder="storage_key"
            />
          </label>
          <label>
            Value
            <textarea
              value={customValue}
              onChange={(e) => setCustomValue(e.target.value)}
              placeholder="Value saved to localStorage"
              rows={4}
            />
          </label>
          <button type="submit" disabled={savingCustom}>
            {savingCustom ? 'Saving...' : 'Save to Local Storage'}
          </button>
        </form>
      </div>

      <div className="card">
        <h3>Local Storage ({localEntries.length})</h3>
        <p style={{ marginBottom: '1em' }}>
          <small>Keys in blocklist ({BLOCKLIST.join(', ')}) are hidden for security.</small>
        </p>
        {localEntries.length === 0 ? (
          <p>No local storage entries (excluding blocklisted keys).</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Key</th>
                <th>Value (max {MAX_VALUE_DISPLAY} chars)</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {localEntries.map((entry) => (
                <tr key={entry.key}>
                  <td><code>{entry.key}</code></td>
                  <td>
                    <code style={{ wordBreak: 'break-all', fontSize: '0.85em' }}>
                      {truncateValue(entry.value)}
                    </code>
                  </td>
                  <td>
                    <div className="button-group" style={{ margin: 0 }}>
                      <button
                        onClick={() => handleSyncToDb(entry.key)}
                        disabled={syncing[`toDb-${entry.key}`]}
                      >
                        {syncing[`toDb-${entry.key}`] ? 'Syncing...' : 'Sync to DB'}
                      </button>
                      <button onClick={() => handleCopy(entry.value, entry.key)}>
                        Copy to clipboard
                      </button>
                      <button onClick={() => handleRemoveFromLocal(entry.key)}>
                        Remove
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <button onClick={refreshLocalEntries} style={{ marginTop: '1em' }}>
          Refresh Local
        </button>
      </div>

      <div className="card">
        <h3>Database Entries ({dbEntries.length})</h3>
        {loading ? (
          <p>Loading...</p>
        ) : dbEntries.length === 0 ? (
          <p>No entries stored in the database yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Key</th>
                <th>Value (max {MAX_VALUE_DISPLAY} chars)</th>
                <th>Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {dbEntries.map((entry) => (
                <tr key={entry.id}>
                  <td><code>{entry.key}</code></td>
                  <td>
                    <code style={{ wordBreak: 'break-all', fontSize: '0.85em' }}>
                      {truncateValue(entry.value)}
                    </code>
                  </td>
                  <td>
                    <small>{new Date(entry.updated_at * 1000).toLocaleString()}</small>
                  </td>
                  <td>
                    <div className="button-group" style={{ margin: 0 }}>
                      <button
                        onClick={() => handleSyncFromDb(entry)}
                        disabled={syncing[`fromDb-${entry.id}`]}
                      >
                        {syncing[`fromDb-${entry.id}`] ? 'Syncing...' : 'Sync to Local'}
                      </button>
                      <button
                        onClick={() => handleCopy(entry.value, entry.key)}
                      >
                        Copy to clipboard
                      </button>
                      <button
                        onClick={() => handleRemoveFromDb(entry)}
                        disabled={syncing[`delDb-${entry.id}`]}
                      >
                        {syncing[`delDb-${entry.id}`] ? 'Removing...' : 'Remove'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <button onClick={loadDbEntries} style={{ marginTop: '1em' }}>
          Refresh DB
        </button>
      </div>
    </div>
  );
}
