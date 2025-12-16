import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';

export default function Metrics() {
  const [metrics, setMetrics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [newMetric, setNewMetric] = useState('');
  const [newValue, setNewValue] = useState('');
  const [adding, setAdding] = useState(false);
  const [hasToken, setHasToken] = useState(!!localStorage.getItem('impulses_token'));

  useEffect(() => {
    loadMetrics();
  }, []);

  async function loadMetrics() {
    try {
      setLoading(true);
      const data = await api.listMetrics();
      setMetrics(data || []);
      setError('');
    } catch (err) {
      setError(err.message || 'Failed to load metrics');
    } finally {
      setLoading(false);
    }
  }

  async function handleAddMetric(e) {
    e.preventDefault();
    if (!newMetric || !newValue) return;

    try {
      setAdding(true);
      setError('');
      const datapoint = {
        value: parseFloat(newValue),
        timestamp: Date.now(),
        dimensions: {}
      };
      await api.addDatapoints(newMetric, [datapoint]);
      setNewMetric('');
      setNewValue('');
      setHasToken(!!localStorage.getItem('impulses_token'));
      loadMetrics();
    } catch (err) {
      setError(err.message || 'Failed to add datapoint');
    } finally {
      setAdding(false);
    }
  }

  if (loading) {
    return <div className="loading">Loading metrics...</div>;
  }

  return (
    <div>
      <h2>Metrics</h2>
      <p>Your tracked metrics. Each metric can contain multiple datapoints.</p>

      {!hasToken && (
        <div className="error">
          <strong>No API token configured!</strong>
          <p>You need to create a SUPER token to use metrics. Go to <Link to="/tokens">Tokens</Link> page, create a SUPER token, and save it for metrics use.</p>
        </div>
      )}

      {error && <div className="error">{error}</div>}

      <div className="card">
        <h3>Add Datapoint</h3>
        <form onSubmit={handleAddMetric}>
          <label>
            Metric Name:
            <input
              type="text"
              value={newMetric}
              onChange={(e) => setNewMetric(e.target.value)}
              placeholder="e.g., transactions, weight, steps"
              required
            />
          </label>

          <label>
            Value:
            <input
              type="number"
              step="any"
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              placeholder="e.g., 100, -50.5"
              required
            />
          </label>

          <button type="submit" disabled={adding}>
            {adding ? 'Adding...' : 'Add Datapoint'}
          </button>
        </form>
      </div>

      {metrics.length === 0 ? (
        <p>No metrics yet. Add your first datapoint above.</p>
      ) : (
        <div>
          <h3>Your Metrics ({metrics.length})</h3>
          {metrics.map((metric) => (
            <div key={metric} className="metric-item">
              <Link to={`/metrics/${encodeURIComponent(metric)}`}>
                <strong>{metric}</strong>
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
