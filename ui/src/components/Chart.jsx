import { useState, useEffect } from 'react';
import { api } from '../api';
import Plot from './plots/Plot';

export default function Chart({ chart, onUpdate, onDelete }) {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (chart.impulses && chart.impulses.length > 0) {
      loadData();
    }
  }, [chart.impulses]);

  async function loadData() {
    setLoading(true);
    setError('');
    const newData = {};

    try {
      for (const impulse of chart.impulses) {
        try {
          const metricData = await api.getMetric(impulse.impulse_expression);
          newData[impulse.impulse_expression] = metricData || [];
        } catch (err) {
          newData[impulse.impulse_expression] = [];
        }
      }
      setData(newData);
    } catch (err) {
      setError('Failed to load data');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chart-container">
      <div className="chart-header">
        <h3>{chart.name || 'Untitled Chart'}</h3>
        <div className="chart-actions">
          <button onClick={loadData} disabled={loading}>
            {loading ? 'Loading...' : 'Refresh'}
          </button>
          <button onClick={() => onDelete(chart.id)}>Delete</button>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      <Plot data={data} impulses={chart.impulses} />

      <div className="chart-legend">
        {chart.impulses.map((impulse, idx) => (
          <div key={idx} className="legend-item">
            <span className="legend-color" style={{ backgroundColor: impulse.color || '#0066cc' }} />
            <span>{impulse.impulse_expression}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
