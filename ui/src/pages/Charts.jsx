import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { format as formatPulseProgram } from '@impulses/sdk-typescript';
import Chart from '../components/Chart';
import { DISPLAY_TYPE_OPTIONS, DISPLAY_TYPE_DEFAULT } from '../lib/displayTypes';

const STORAGE_KEY = 'impulses_charts';
const DEFAULT_COLOR = '#0066cc';

const RESOLUTION_OPTIONS = [
  { value: 'raw', label: 'Raw' },
  { value: 'day', label: 'Day' },
  { value: 'week', label: 'Week' },
  { value: 'two_weeks', label: 'Two weeks' },
  { value: 'month', label: 'Month' },
];

const ROLLUP_OPTIONS = [
  { value: 'last', label: 'Last' },
  { value: 'sum', label: 'Sum' },
  { value: 'average', label: 'Average' },
  { value: 'min', label: 'Min' },
  { value: 'max', label: 'Max' },
];

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
  formDefaultZoomWindow,
  setFormDefaultZoomWindow,
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
            className="textarea-fullwidth"
            required
          />
          <div className="button-group">
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

        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={formFormatYAsDurationMs}
            onChange={e => setFormFormatYAsDurationMs(e.target.checked)}
          />
          Render Y values as durations (ms)
        </label>

        <br />

        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={formInterpolateToLatest}
            onChange={e => setFormInterpolateToLatest(e.target.checked)}
          />
          Extend line series to latest timestamp
        </label>

        <br />

        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={formCutFutureDatapoints}
            onChange={e => setFormCutFutureDatapoints(e.target.checked)}
          />
          Hide datapoints after now
        </label>

        <div>
          <label>Default Zoom Window</label>
          <input
            type="text"
            value={formDefaultZoomWindow}
            onChange={e => setFormDefaultZoomWindow(e.target.value)}
            placeholder="e.g. -180d or -30d:0d"
            style={{ maxWidth: '200px' }}
          />
          <p className="layout-empty-hint">Leave empty for no default zoom. Examples: -180d, -30d:7d</p>
        </div>

        <div className="impulses-section">
          <h4>Variables</h4>
          {formVariables.map((variable, idx) => (
            <div key={idx} className="variable-block">
              <div className="impulse-row">
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
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={!!variable.useRightAxis}
                    onChange={e => handleVariableChange(idx, 'useRightAxis', e.target.checked)}
                  />
                  Right axis
                </label>
                <button type="button" onClick={() => handleRemoveVariable(idx)}>Remove</button>
              </div>
              <div className="variable-settings-row">
                <label className="variable-setting">
                  <span>Alias:</span>
                  <input
                    type="text"
                    value={variable.alias || ''}
                    onChange={e => handleVariableChange(idx, 'alias', e.target.value)}
                    placeholder="Display name"
                  />
                </label>
                <label className="variable-setting">
                  <span>Resolution:</span>
                  <select
                    value={variable.resolution || 'raw'}
                    onChange={e => handleVariableChange(idx, 'resolution', e.target.value)}
                  >
                    {RESOLUTION_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </label>
                <label className="variable-setting">
                  <span>Roll-up:</span>
                  <select
                    value={variable.rollUp || 'last'}
                    onChange={e => handleVariableChange(idx, 'rollUp', e.target.value)}
                    disabled={!variable.resolution || variable.resolution === 'raw'}
                  >
                    {ROLLUP_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </label>
              </div>
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
  const { chartId } = useParams();
  const navigate = useNavigate();

  const [chartsMap, setChartsMap] = useState(loadChartsFromStorage);
  const [isEditing, setIsEditing] = useState(false);

  const charts = Object.values(chartsMap);
  const currentChart = chartId ? chartsMap[chartId] : null;

  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formProgram, setFormProgram] = useState('');
  const [formVariables, setFormVariables] = useState([]);
  const [formFormatYAsDurationMs, setFormFormatYAsDurationMs] = useState(false);
  const [formInterpolateToLatest, setFormInterpolateToLatest] = useState(false);
  const [formCutFutureDatapoints, setFormCutFutureDatapoints] = useState(false);
  const [formDefaultZoomWindow, setFormDefaultZoomWindow] = useState('');
  const [isCreatingNew, setIsCreatingNew] = useState(false);

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
    setFormDefaultZoomWindow('');
    setIsEditing(false);
    setIsCreatingNew(false);
  }

  function handleCreateNew() {
    resetForm();
    setIsCreatingNew(true);
  }

  function handleToggleEdit() {
    if (isEditing) {
      resetForm();
    } else if (currentChart) {
      setFormName(currentChart.name);
      setFormDescription(currentChart.description || '');
      setFormProgram(currentChart.program || '');
      setFormVariables(currentChart.variables?.map(variable => ({
        ...variable,
        useRightAxis: !!variable.useRightAxis,
      })) || []);
      setFormFormatYAsDurationMs(!!currentChart.formatYAsDurationMs);
      setFormInterpolateToLatest(!!currentChart.interpolateToLatest);
      setFormCutFutureDatapoints(!!currentChart.cutFutureDatapoints);
      setFormDefaultZoomWindow(currentChart.defaultZoomWindow || '');
      setIsEditing(true);
    }
  }

  function handleAddVariable() {
    setFormVariables([
      ...formVariables,
      { variable: '', color: DEFAULT_COLOR, displayType: DISPLAY_TYPE_DEFAULT, useRightAxis: false, alias: '', resolution: 'raw', rollUp: 'last' },
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

    const newId = isCreatingNew ? generateId() : currentChart?.id;
    const chartData = {
      id: newId,
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
      defaultZoomWindow: formDefaultZoomWindow.trim() || null,
      createdAt: isCreatingNew ? Date.now() : (currentChart?.createdAt || Date.now()),
      updatedAt: Date.now(),
    };

    upsertChart(chartData);
    resetForm();

    if (isCreatingNew) {
      navigate(`/charts/${newId}`);
    }
  }

  function handleDelete(id) {
    if (confirm('Delete this chart?')) {
      setChartsMap(prev => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      resetForm();
      navigate('/charts');
    }
  }

  function handleUpdate(updatedChart) {
    upsertChart(updatedChart);
  }

  const hasCharts = charts.length > 0;

  return (
    <div>
      {/* Chart Picker */}
      <div className="dashboard-picker">
        <div className="dashboard-tabs">
          {charts.map((chart) => (
            <Link
              key={chart.id}
              to={`/charts/${chart.id}`}
              className={`dashboard-tab ${chartId === chart.id ? 'active' : ''}`}
            >
              {chart.name || 'Untitled'}
            </Link>
          ))}
          <button
            type="button"
            className="dashboard-tab dashboard-tab--new"
            onClick={handleCreateNew}
          >
            + New
          </button>
          {chartId && currentChart && (
            <button
              type="button"
              className="dashboard-tab"
              onClick={handleToggleEdit}
            >
              {isEditing ? 'Cancel Edit' : 'Edit'}
            </button>
          )}
        </div>
      </div>

      {/* New Chart Form */}
      {isCreatingNew && (
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
          formDefaultZoomWindow={formDefaultZoomWindow}
          setFormDefaultZoomWindow={setFormDefaultZoomWindow}
          handleVariableChange={handleVariableChange}
          handleRemoveVariable={handleRemoveVariable}
          handleAddVariable={handleAddVariable}
          handleSubmit={handleSubmit}
          onCancel={resetForm}
          onDelete={handleDelete}
          editingChart={null}
        />
      )}

      {/* No chart selected prompt */}
      {!chartId && !isCreatingNew && (
        <div className="card">
          <p>
            {hasCharts
              ? 'Select a chart from the tabs above to view it.'
              : 'No charts yet. Click "+ New" to create your first chart.'}
          </p>
        </div>
      )}

      {/* Edit form for current chart */}
      {chartId && currentChart && isEditing && (
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
          formDefaultZoomWindow={formDefaultZoomWindow}
          setFormDefaultZoomWindow={setFormDefaultZoomWindow}
          handleVariableChange={handleVariableChange}
          handleRemoveVariable={handleRemoveVariable}
          handleAddVariable={handleAddVariable}
          handleSubmit={handleSubmit}
          onCancel={resetForm}
          onDelete={handleDelete}
          editingChart={currentChart}
        />
      )}

      {/* Current chart display */}
      {chartId && currentChart && !isEditing && (
        <div className="chart-wrapper">
          <Chart
            chart={currentChart}
            onUpdate={handleUpdate}
            onDelete={handleDelete}
          />
        </div>
      )}

      {/* Chart not found */}
      {chartId && !currentChart && (
        <div className="card">
          <p>Chart not found. It may have been deleted.</p>
        </div>
      )}
    </div>
  );
}
