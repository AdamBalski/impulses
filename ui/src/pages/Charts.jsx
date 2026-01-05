import { useState, useEffect, useRef } from 'react';
import { format as formatPulseProgram } from '@impulses/sdk-typescript';
import Chart from '../components/Chart';

const STORAGE_KEY = 'impulses_charts';
const DEFAULT_COLOR = '#0066cc';

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

function ChartForm({
  title,
  submitLabel,
  formName,
  setFormName,
  formDescription,
  setFormDescription,
  formProgram,
  setFormProgram,
  formVariables,
  formFormatYAsDurationMs,
  setFormFormatYAsDurationMs,
  handleVariableChange,
  handleRemoveVariable,
  handleAddVariable,
  handleSubmit,
  onCancel,
}) {
  const programTextareaRef = useRef(null);

  useEffect(() => {
    if (programTextareaRef.current) {
      const textarea = programTextareaRef.current;
      textarea.style.height = 'auto';
      textarea.style.height = `${textarea.scrollHeight}px`;
    }
  }, [formProgram]);

  const handleProgramChange = (e) => {
    const textarea = e.target;
    textarea.style.height = 'auto';
    textarea.style.height = `${textarea.scrollHeight}px`;
    setFormProgram(textarea.value);
  };

  return (
    <div className="card chart-form">
      <h3>{title}</h3>
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

        <div>
          <label>PulseLang Program</label>
          <textarea
            ref={programTextareaRef}
            value={formProgram}
            onChange={handleProgramChange}
            placeholder={'(define foo (data "metric"))'}
            rows={6}
            style={{ width: '100%', maxWidth: 'none' }}
            required
          />
          <div className="button-group" style={{ marginTop: '0.5rem' }}>
            <button
              type="button"
              onClick={() => {
                try {
                  const formatted = formatPulseProgram(formProgram);
                  setFormProgram(formatted);
                } catch (err) {
                  alert(`Failed to format program: ${err instanceof Error ? err.message : err}`);
                }
              }}
            >
              Format Program
            </button>
          </div>
        </div>

        <label style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'flex-start', gap: '6px', whiteSpace: 'nowrap' }}>
          <input
            type="checkbox"
            checked={formFormatYAsDurationMs}
            onChange={e => setFormFormatYAsDurationMs(e.target.checked)}
          />
          Render Y values as durations (ms)
        </label>

        <div className="impulses-section">
          <h4>Variables</h4>
          {formVariables.map((variable, idx) => (
            <div key={idx} className="impulse-row">
              <input
                type="text"
                value={variable.variable}
                onChange={e => handleVariableChange(idx, 'variable', e.target.value)}
                placeholder="Variable name"
                required
              />
              <select
                value={variable.displayType || 'line'}
                onChange={e => handleVariableChange(idx, 'displayType', e.target.value)}
              >
                <option value="line">Line</option>
                <option value="dots">Dots</option>
                <option value="bar">Bars</option>
              </select>
              <input
                type="color"
                value={variable.color}
                onChange={e => handleVariableChange(idx, 'color', e.target.value)}
              />
              <button type="button" onClick={() => handleRemoveVariable(idx)}>Remove</button>
            </div>
          ))}
          <button type="button" onClick={handleAddVariable}>Add Variable</button>
        </div>

        <div className="button-group">
          <button type="submit">{submitLabel}</button>
          <button type="button" onClick={onCancel}>Cancel</button>
        </div>
      </form>
    </div>
  );
}

export default function Charts() {
  const [charts, setCharts] = useState(loadChartsFromStorage);
  const [showForm, setShowForm] = useState(false);
  const [editingChart, setEditingChart] = useState(null);

  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formProgram, setFormProgram] = useState('');
  const [formVariables, setFormVariables] = useState([]);
  const [formFormatYAsDurationMs, setFormFormatYAsDurationMs] = useState(false);

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
    setFormProgram('');
    setFormVariables([]);
    setFormFormatYAsDurationMs(false);
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
    setFormProgram(chart.program || '');
    setFormVariables([...chart.variables]);
    setFormFormatYAsDurationMs(!!chart.formatYAsDurationMs);
    setEditingChart(chart);
    setShowForm(true);
  }

  function handleAddVariable() {
    setFormVariables([
      ...formVariables,
      { variable: '', color: DEFAULT_COLOR, displayType: 'line' },
    ]);
  }

  function handleRemoveVariable(index) {
    setFormVariables(formVariables.filter((_, i) => i !== index));
  }

  function handleVariableChange(index, field, value) {
    const updated = [...formVariables];
    updated[index] = { ...updated[index], [field]: value };
    setFormVariables(updated);
  }

  function handleSubmit(e) {
    e.preventDefault();

    const chartData = {
      id: editingChart?.id || generateId(),
      name: formName,
      description: formDescription,
      program: formProgram,
      variables: formVariables.filter(v => v.variable.trim()),
      formatYAsDurationMs: !!formFormatYAsDurationMs,
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
        <ChartForm
          title="New Chart"
          submitLabel="Create"
          formName={formName}
          setFormName={setFormName}
          formDescription={formDescription}
          setFormDescription={setFormDescription}
          formProgram={formProgram}
          setFormProgram={setFormProgram}
          formVariables={formVariables}
          formFormatYAsDurationMs={formFormatYAsDurationMs}
          setFormFormatYAsDurationMs={setFormFormatYAsDurationMs}
          handleVariableChange={handleVariableChange}
          handleRemoveVariable={handleRemoveVariable}
          handleAddVariable={handleAddVariable}
          handleSubmit={handleSubmit}
          onCancel={resetForm}
        />
      )}

      {charts.length === 0 && !showForm && (
        <p>No charts yet. Create one to get started.</p>
      )}

      {charts.map(chart => (
        <div key={chart.id} className="chart-wrapper">
          {editingChart?.id === chart.id && (
            <ChartForm
              title="Edit Chart"
              submitLabel="Update"
              formName={formName}
              setFormName={setFormName}
              formDescription={formDescription}
              setFormDescription={setFormDescription}
              formProgram={formProgram}
              setFormProgram={setFormProgram}
              formVariables={formVariables}
              formFormatYAsDurationMs={formFormatYAsDurationMs}
              setFormFormatYAsDurationMs={setFormFormatYAsDurationMs}
              handleVariableChange={handleVariableChange}
              handleRemoveVariable={handleRemoveVariable}
              handleAddVariable={handleAddVariable}
              handleSubmit={handleSubmit}
              onCancel={resetForm}
            />
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
