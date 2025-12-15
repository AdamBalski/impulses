import { useState, useEffect, useRef } from 'react';
import Chart from '../components/Chart';

const STORAGE_KEY = 'impulses_charts';

function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

function loadChartsFromStorage() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function saveChartsToStorage(charts) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(charts));
}

export default function Charts() {
  const [charts, setCharts] = useState(loadChartsFromStorage);
  const [showForm, setShowForm] = useState(false);
  const [editingChart, setEditingChart] = useState(null);

  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formImpulses, setFormImpulses] = useState([]);

  const isInitialMount = useRef(true);

  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    saveChartsToStorage(charts);
  }, [charts]);

  function resetForm() {
    setFormName('');
    setFormDescription('');
    setFormImpulses([]);
    setEditingChart(null);
    setShowForm(false);
  }

  function handleCreateNew() {
    resetForm();
    setShowForm(true);
  }

  function handleEdit(chart) {
    setFormName(chart.name);
    setFormDescription(chart.description || '');
    setFormImpulses([...chart.impulses]);
    setEditingChart(chart);
    setShowForm(true);
  }

  function handleAddImpulse() {
    setFormImpulses([...formImpulses, { impulse_expression: '', color: '#0066cc', displayType: 'line' }]);
  }

  function handleRemoveImpulse(index) {
    setFormImpulses(formImpulses.filter((_, i) => i !== index));
  }

  function handleImpulseChange(index, field, value) {
    const updated = [...formImpulses];
    updated[index] = { ...updated[index], [field]: value };
    setFormImpulses(updated);
  }

  function handleSubmit(e) {
    e.preventDefault();

    const chartData = {
      id: editingChart?.id || generateId(),
      name: formName,
      description: formDescription,
      impulses: formImpulses.filter(i => i.impulse_expression.trim()),
      createdAt: editingChart?.createdAt || Date.now(),
      updatedAt: Date.now(),
    };

    if (editingChart) {
      setCharts(charts.map(c => c.id === editingChart.id ? chartData : c));
    } else {
      setCharts([...charts, chartData]);
    }

    resetForm();
  }

  function handleDelete(chartId) {
    if (confirm('Delete this chart?')) {
      setCharts(charts.filter(c => c.id !== chartId));
    }
  }

  function handleUpdate(updatedChart) {
    setCharts(charts.map(c => c.id === updatedChart.id ? updatedChart : c));
  }

  return (
    <div>
      <h2>Charts</h2>

      <div className="button-group">
        <button onClick={handleCreateNew}>Create New Chart</button>
      </div>

      {showForm && !editingChart && (
        <div className="card chart-form">
          <h3>New Chart</h3>
          <form onSubmit={handleSubmit}>
            <div>
              <label>Name</label>
              <input
                type="text"
                value={formName}
                onChange={e => setFormName(e.target.value)}
                placeholder="Chart name"
                required
              />
            </div>

            <div>
              <label>Description</label>
              <textarea
                value={formDescription}
                onChange={e => setFormDescription(e.target.value)}
                placeholder="Optional description"
              />
            </div>

            <div className="impulses-section">
              <h4>Impulses (Metrics)</h4>
              {formImpulses.map((impulse, idx) => (
                <div key={idx} className="impulse-row">
                  <input
                    type="text"
                    value={impulse.impulse_expression}
                    onChange={e => handleImpulseChange(idx, 'impulse_expression', e.target.value)}
                    placeholder="Metric name"
                    style={{ flex: 1 }}
                  />
                  <select
                    value={impulse.displayType || 'line'}
                    onChange={e => handleImpulseChange(idx, 'displayType', e.target.value)}
                    style={{ width: '80px' }}
                  >
                    <option value="line">Line</option>
                    <option value="dots">Dots</option>
                  </select>
                  <input
                    type="color"
                    value={impulse.color}
                    onChange={e => handleImpulseChange(idx, 'color', e.target.value)}
                    style={{ width: '50px', padding: '0.25em' }}
                  />
                  <button type="button" onClick={() => handleRemoveImpulse(idx)}>Remove</button>
                </div>
              ))}
              <button type="button" onClick={handleAddImpulse}>Add Impulse</button>
            </div>

            <div className="button-group">
              <button type="submit">Create</button>
              <button type="button" onClick={resetForm}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {charts.length === 0 && !showForm && (
        <p>No charts yet. Create one to get started.</p>
      )}

      {charts.map(chart => (
        <div key={chart.id} className="chart-wrapper">
          {editingChart?.id === chart.id && (
            <div className="card chart-form">
              <h3>Edit Chart</h3>
              <form onSubmit={handleSubmit}>
                <div>
                  <label>Name</label>
                  <input
                    type="text"
                    value={formName}
                    onChange={e => setFormName(e.target.value)}
                    placeholder="Chart name"
                    required
                  />
                </div>

                <div>
                  <label>Description</label>
                  <textarea
                    value={formDescription}
                    onChange={e => setFormDescription(e.target.value)}
                    placeholder="Optional description"
                  />
                </div>

                <div className="impulses-section">
                  <h4>Impulses (Metrics)</h4>
                  {formImpulses.map((impulse, idx) => (
                    <div key={idx} className="impulse-row">
                      <input
                        type="text"
                        value={impulse.impulse_expression}
                        onChange={e => handleImpulseChange(idx, 'impulse_expression', e.target.value)}
                        placeholder="Metric name"
                        style={{ flex: 1 }}
                      />
                      <select
                        value={impulse.displayType || 'line'}
                        onChange={e => handleImpulseChange(idx, 'displayType', e.target.value)}
                        style={{ width: '80px' }}
                      >
                        <option value="line">Line</option>
                        <option value="dots">Dots</option>
                      </select>
                      <input
                        type="color"
                        value={impulse.color}
                        onChange={e => handleImpulseChange(idx, 'color', e.target.value)}
                        style={{ width: '50px', padding: '0.25em' }}
                      />
                      <button type="button" onClick={() => handleRemoveImpulse(idx)}>Remove</button>
                    </div>
                  ))}
                  <button type="button" onClick={handleAddImpulse}>Add Impulse</button>
                </div>

                <div className="button-group">
                  <button type="submit">Update</button>
                  <button type="button" onClick={resetForm}>Cancel</button>
                </div>
              </form>
            </div>
          )}
          <Chart
            chart={chart}
            onUpdate={handleUpdate}
            onDelete={handleDelete}
          />
          <button onClick={() => handleEdit(chart)} className="edit-chart-btn">
            Edit Chart Settings
          </button>
        </div>
      ))}
    </div>
  );
}
