import { useState, useEffect, useRef } from 'react';
import { format as formatPulseProgram } from '@impulses/sdk-typescript';
import Chart from '../components/Chart';
import { DISPLAY_TYPE_OPTIONS, DISPLAY_TYPE_DEFAULT } from '../lib/displayTypes';

const STORAGE_KEY = 'impulses_charts';
const DEFAULT_COLOR = '#0066cc';

function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

function loadChartsFromStorage() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return {};
    return JSON.parse(stored);
  } catch {
    return {};
  }
}

function saveChartsToStorage(chartsMap) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(chartsMap));
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
  formInterpolateToLatest,
  setFormInterpolateToLatest,
  formCutFutureDatapoints,
  setFormCutFutureDatapoints,
  handleVariableChange,
  handleRemoveVariable,
  handleAddVariable,
  handleSubmit,
  onCancel,
  onDelete,
  editingChart,
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

        <br />

        <label style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'flex-start', gap: '6px', whiteSpace: 'nowrap' }}>
          <input
            type="checkbox"
            checked={formInterpolateToLatest}
            onChange={e => setFormInterpolateToLatest(e.target.checked)}
          />
          Extend line series to latest timestamp
        </label>

        <br />

        <label style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'flex-start', gap: '6px', whiteSpace: 'nowrap' }}>
          <input
            type="checkbox"
            checked={formCutFutureDatapoints}
            onChange={e => setFormCutFutureDatapoints(e.target.checked)}
          />
          Hide datapoints after now
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
                value={variable.displayType || DISPLAY_TYPE_DEFAULT}
                onChange={e => handleVariableChange(idx, 'displayType', e.target.value)}
              >
                {DISPLAY_TYPE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option.charAt(0).toUpperCase() + option.slice(1)}
                  </option>
                ))}
              </select>
              <input
                type="color"
                value={variable.color}
                onChange={e => handleVariableChange(idx, 'color', e.target.value)}
              />
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                <input
                  type="checkbox"
                  checked={!!variable.useRightAxis}
                  onChange={e => handleVariableChange(idx, 'useRightAxis', e.target.checked)}
                />
                Right axis
              </label>
              <button type="button" onClick={() => handleRemoveVariable(idx)}>Remove</button>
            </div>
          ))}
          <button type="button" onClick={handleAddVariable}>Add Variable</button>
        </div>

        <div className="button-group">
          <button type="submit">{submitLabel}</button>
          <button type="button" onClick={onCancel}>Cancel</button>
          {editingChart && (
            <button
              type="button"
              onClick={() => {
                if (confirm(`Delete chart "${editingChart.name}"? This cannot be undone.`)) {
                  onDelete(editingChart.id);
                  onCancel();
                }
              }}
            >
              Delete Chart
            </button>
          )}
        </div>
      </form>
    </div>
  );
}

export default function Charts() {
  const [chartsMap, setChartsMap] = useState(loadChartsFromStorage);
  const [showForm, setShowForm] = useState(false);
  const [editingChart, setEditingChart] = useState(null);

  const charts = Object.values(chartsMap);

  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formProgram, setFormProgram] = useState('');
  const [formVariables, setFormVariables] = useState([]);
  const [formFormatYAsDurationMs, setFormFormatYAsDurationMs] = useState(false);
  const [formInterpolateToLatest, setFormInterpolateToLatest] = useState(false);
  const [formCutFutureDatapoints, setFormCutFutureDatapoints] = useState(false);

  const isInitialMount = useRef(true);

  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    saveChartsToStorage(chartsMap);
  }, [chartsMap]);

  function resetForm() {
    setFormName('');
    setFormDescription('');
    setFormProgram('');
    setFormVariables([]);
    setFormFormatYAsDurationMs(false);
    setFormInterpolateToLatest(false);
    setFormCutFutureDatapoints(false);
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
    setFormVariables(chart.variables.map(variable => ({
      ...variable,
      useRightAxis: !!variable.useRightAxis,
    })));
    setFormFormatYAsDurationMs(!!chart.formatYAsDurationMs);
    setFormInterpolateToLatest(!!chart.interpolateToLatest);
    setFormCutFutureDatapoints(!!chart.cutFutureDatapoints);
    setEditingChart(chart);
    setShowForm(true);
  }

  function handleAddVariable() {
    setFormVariables([
      ...formVariables,
      { variable: '', color: DEFAULT_COLOR, displayType: DISPLAY_TYPE_DEFAULT, useRightAxis: false },
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

  function upsertChart(chartData) {
    setChartsMap(prev => ({
      ...prev,
      [chartData.id]: chartData,
    }));
  }

  function handleSubmit(e) {
    e.preventDefault();

    const chartData = {
      id: editingChart?.id || generateId(),
      name: formName,
      description: formDescription,
      program: formProgram,
      variables: formVariables
        .filter(v => v.variable.trim())
        .map(v => ({
          ...v,
          useRightAxis: !!v.useRightAxis,
        })),
      formatYAsDurationMs: !!formFormatYAsDurationMs,
      interpolateToLatest: !!formInterpolateToLatest,
      cutFutureDatapoints: !!formCutFutureDatapoints,
      createdAt: editingChart?.createdAt || Date.now(),
      updatedAt: Date.now(),
    };

    upsertChart(chartData);

    resetForm();
  }

  function handleDelete(chartId) {
    if (confirm('Delete this chart?')) {
      setChartsMap(prev => {
        const next = { ...prev };
        delete next[chartId];
        return next;
      });
    }
  }

  function handleUpdate(updatedChart) {
    upsertChart(updatedChart);
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
          formInterpolateToLatest={formInterpolateToLatest}
          setFormInterpolateToLatest={setFormInterpolateToLatest}
          formCutFutureDatapoints={formCutFutureDatapoints}
          setFormCutFutureDatapoints={setFormCutFutureDatapoints}
          handleVariableChange={handleVariableChange}
          handleRemoveVariable={handleRemoveVariable}
          handleAddVariable={handleAddVariable}
          handleSubmit={handleSubmit}
          onCancel={resetForm}
          onDelete={handleDelete}
          editingChart={null}
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
              formInterpolateToLatest={formInterpolateToLatest}
              setFormInterpolateToLatest={setFormInterpolateToLatest}
              formCutFutureDatapoints={formCutFutureDatapoints}
              setFormCutFutureDatapoints={setFormCutFutureDatapoints}
              handleVariableChange={handleVariableChange}
              handleRemoveVariable={handleRemoveVariable}
              handleAddVariable={handleAddVariable}
              handleSubmit={handleSubmit}
              onCancel={resetForm}
              onDelete={handleDelete}
              editingChart={editingChart}
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
