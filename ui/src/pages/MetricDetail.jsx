import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { api } from '../api';

export default function MetricDetail() {
  const { name } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    loadMetric();
  }, [name]);

  async function loadMetric() {
    try {
      setLoading(true);
      const metricData = await api.getMetric(name);
      setData(metricData);
      setError('');
    } catch (err) {
      setError(err.message || 'Failed to load metric');
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    if (!confirm(`Delete metric "${name}" and all its datapoints?`)) {
      return;
    }

    try {
      setDeleting(true);
      await api.deleteMetric(name);
      navigate('/metrics');
    } catch (err) {
      setError(err.message || 'Failed to delete metric');
      setDeleting(false);
    }
  }

  if (loading) {
    return <div className="loading">Loading metric...</div>;
  }

  if (error) {
    return (
      <div>
        <div className="error">{error}</div>
        <Link to="/metrics">← Back to Metrics</Link>
      </div>
    );
  }

  return (
    <div>
      <Link to="/metrics">← Back to Metrics</Link>
      
      <h2>{name}</h2>
      <p>Datapoints: <strong>{data?.length || 0}</strong></p>

      <div className="button-group">
        <button onClick={handleDelete} disabled={deleting}>
          {deleting ? 'Deleting...' : 'Delete Metric'}
        </button>
      </div>

      {data && data.length > 0 ? (
        <div>
          <h3>Recent Datapoints</h3>
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Value</th>
                <th>Dimensions</th>
              </tr>
            </thead>
            <tbody>
              {data.slice(0, 100).map((dp, idx) => (
                <tr key={idx}>
                  <td>{new Date(dp.timestamp * 1000).toLocaleString()}</td>
                  <td>{dp.value}</td>
                  <td>{JSON.stringify(dp.dimensions)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.length > 100 && (
            <p><em>Showing first 100 of {data.length} datapoints</em></p>
          )}
        </div>
      ) : (
        <p>No datapoints yet.</p>
      )}
    </div>
  );
}
