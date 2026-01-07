import { useState, useEffect, useMemo, useRef } from 'react';
import { format as formatPulseProgram } from '@impulses/sdk-typescript';

export default function DashboardEditor({
  dashboard,
  chartsMap,
  onSave,
  onDelete,
  onCancel,
  onCopy,
}) {
  const [name, setName] = useState(dashboard?.name || '');
  const [description, setDescription] = useState(dashboard?.description || '');
  const [program, setProgram] = useState(dashboard?.program || '');
  const [defaultZoomWindow, setDefaultZoomWindow] = useState(dashboard?.defaultZoomWindow || '');
  const [overrideChartZoom, setOverrideChartZoom] = useState(!!dashboard?.overrideChartZoom);
  const programTextareaRef = useRef(null);
  const [layout, setLayout] = useState(
    (dashboard?.layout || []).map((item) => ({
      chartId: item.chartId || '',
      width: item.width != null ? String(item.width) : '',
      height: item.height != null ? String(item.height) : '',
      interpolateToLatest: !!item.interpolateToLatest,
    }))
  );

  useEffect(() => {
    setName(dashboard?.name || '');
    setDescription(dashboard?.description || '');
    setProgram(dashboard?.program || '');
    setDefaultZoomWindow(dashboard?.defaultZoomWindow || '');
    setOverrideChartZoom(!!dashboard?.overrideChartZoom);
    setLayout(
      (dashboard?.layout || []).map((item) => ({
        chartId: item.chartId || '',
        width: item.width != null ? String(item.width) : '',
        height: item.height != null ? String(item.height) : '',
        interpolateToLatest: !!item.interpolateToLatest,
      }))
    );
  }, [dashboard]);

  const chartOptions = Object.entries(chartsMap).map(([id, chart]) => ({
    id,
    name: chart.name || id,
  }));

  const WIDTH_MIN = 10;
  const WIDTH_MAX = 60;
  const HEIGHT_MIN = 8;
  const HEIGHT_MAX = 40;

  const layoutErrors = useMemo(() => {
    return layout.map((item) => {
      const widthNumber = Number(item.width);
      const heightNumber = Number(item.height);
      const widthError =
        item.width === ''
          ? 'Required'
          : Number.isNaN(widthNumber)
            ? 'Must be a number'
            : widthNumber < WIDTH_MIN || widthNumber > WIDTH_MAX
              ? `Must be ${WIDTH_MIN}-${WIDTH_MAX}`
              : null;
      const heightError =
        item.height === ''
          ? 'Required'
          : Number.isNaN(heightNumber)
            ? 'Must be a number'
            : heightNumber < HEIGHT_MIN || heightNumber > HEIGHT_MAX
              ? `Must be ${HEIGHT_MIN}-${HEIGHT_MAX}`
              : null;
      const chartError = !item.chartId ? 'Select a chart' : null;
      return { widthError, heightError, chartError };
    });
  }, [layout]);

  function handleAddChart() {
    setLayout([
      ...layout,
      { chartId: chartOptions[0]?.id || '', width: '15', height: '15', interpolateToLatest: false },
    ]);
  }

  function handleRemoveChart(index) {
    setLayout(layout.filter((_, i) => i !== index));
  }

  function handleChartChange(index, field, value) {
    const newLayout = [...layout];
    if (field === 'width' || field === 'height') {
      const sanitized = value.replace(/[^0-9]/g, '');
      newLayout[index] = { ...newLayout[index], [field]: sanitized };
    } else if (field === 'interpolateToLatest') {
      newLayout[index] = { ...newLayout[index], interpolateToLatest: value };
    } else {
      newLayout[index] = { ...newLayout[index], [field]: value };
    }
    setLayout(newLayout);
  }

  function handleMoveUp(index) {
    if (index === 0) return;
    const newLayout = [...layout];
    [newLayout[index - 1], newLayout[index]] = [newLayout[index], newLayout[index - 1]];
    setLayout(newLayout);
  }

  function handleMoveDown(index) {
    if (index === layout.length - 1) return;
    const newLayout = [...layout];
    [newLayout[index], newLayout[index + 1]] = [newLayout[index + 1], newLayout[index]];
    setLayout(newLayout);
  }

  function handleSave() {
    const validatedLayout = [];
    for (let i = 0; i < layout.length; i += 1) {
      const item = layout[i];
      const widthNumber = Number(item.width);
      const heightNumber = Number(item.height);
      if (
        !item.chartId ||
        Number.isNaN(widthNumber) ||
        Number.isNaN(heightNumber) ||
        widthNumber < WIDTH_MIN ||
        widthNumber > WIDTH_MAX ||
        heightNumber < HEIGHT_MIN ||
        heightNumber > HEIGHT_MAX
      ) {
        alert('Please fix layout validation errors before saving.');
        return;
      }
      validatedLayout.push({
        chartId: item.chartId,
        width: widthNumber,
        height: heightNumber,
        interpolateToLatest: !!item.interpolateToLatest,
      });
    }
    onSave({
      ...dashboard,
      name,
      description,
      program,
      defaultZoomWindow: defaultZoomWindow.trim() || null,
      overrideChartZoom: !!overrideChartZoom,
      layout: validatedLayout,
    });
  }

  function handleDelete() {
    if (window.confirm(`Are you sure you want to delete dashboard "${name}"?`)) {
      onDelete(dashboard.id);
    }
  }

  function handleConcatenatePrograms() {
    const referencedChartPrograms = layout
      .map((item) => chartsMap[item.chartId]?.program?.trim())
      .filter((prog) => typeof prog === 'string' && prog.length > 0);

    if (referencedChartPrograms.length === 0) {
      alert('No PulseLang programs found in the charts referenced by this dashboard.');
      return;
    }

    if (
      !window.confirm(
        'Replace the dashboard PulseLang program with a concatenation of all referenced chart programs? This will overwrite the current dashboard program.'
      )
    ) {
      return;
    }

    const concatenated = referencedChartPrograms.join('\n\n');
    setProgram(concatenated);
  }

  return (
    <div className="dashboard-editor card">
      <h3>Edit Dashboard</h3>

      <div className="form-row">
        <label>ID (readonly)</label>
        <input type="text" value={dashboard?.id || ''} readOnly disabled />
      </div>

      <div className="form-row">
        <label>Name</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Dashboard name"
        />
      </div>

      <div className="form-row">
        <label>Description</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Optional description"
          rows={2}
        />
      </div>

      <div className="form-row">
        <label>PulseLang Program (optional)</label>
        <p className="layout-empty-hint">
          Define variables here to share data across all charts. Charts will use these variables instead of computing their own programs.
        </p>
        <textarea
          ref={programTextareaRef}
          value={program}
          onChange={(e) => setProgram(e.target.value)}
          placeholder={'(define shared-data (data "metric"))\n(define processed (moving-avg shared-data 7))'}
          rows={4}
          className="textarea-fullwidth"
        />
        <div className="button-group">
          <button
            type="button"
            onClick={() => {
              try {
                const formatted = formatPulseProgram(program);
                setProgram(formatted);
              } catch (err) {
                alert(`Failed to format program: ${err instanceof Error ? err.message : err}`);
              }
            }}
            disabled={!program.trim()}
          >
            Format Program
          </button>
          <button
            type="button"
            onClick={handleConcatenatePrograms}
            disabled={layout.length === 0}
          >
            Concatenate Chart Programs
          </button>
        </div>
      </div>

      <div className="form-row">
        <label>Default Zoom Window</label>
        <input
          type="text"
          value={defaultZoomWindow}
          onChange={(e) => setDefaultZoomWindow(e.target.value)}
          placeholder="e.g. -180d or -30d:0d"
          style={{ maxWidth: '200px' }}
        />
        <p className="layout-empty-hint">Leave empty for no default zoom. Examples: -180d, -30d:7d</p>
        <label className="checkbox-label" style={{ marginTop: '0.5em' }}>
          <input
            type="checkbox"
            checked={overrideChartZoom}
            onChange={(e) => setOverrideChartZoom(e.target.checked)}
            disabled={!defaultZoomWindow.trim()}
          />
          Override individual chart zoom settings
        </label>
      </div>

      <div className="form-row">
        <label>Layout</label>
        <div className="layout-list">
          {layout.length === 0 && (
            <p className="layout-empty-hint">No charts in layout. Click "Add Chart" to add one.</p>
          )}
          {layout.map((item, index) => (
            <div key={index} className="layout-row">
              <select
                value={item.chartId}
                onChange={(e) => handleChartChange(index, 'chartId', e.target.value)}
              >
                <option value="">-- Select Chart --</option>
                {chartOptions.map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.name}
                  </option>
                ))}
              </select>
              <div className="layout-input">
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  value={item.width}
                  onChange={(e) => handleChartChange(index, 'width', e.target.value)}
                  title={`Width (${WIDTH_MIN}-${WIDTH_MAX})`}
                  placeholder={`${WIDTH_MIN}-${WIDTH_MAX}`}
                />
                {layoutErrors[index]?.widthError && (
                  <div className="field-error">{layoutErrors[index].widthError}</div>
                )}
              </div>
              <span>×</span>
              <div className="layout-input">
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  value={item.height}
                  onChange={(e) => handleChartChange(index, 'height', e.target.value)}
                  title={`Height (${HEIGHT_MIN}-${HEIGHT_MAX})`}
                  placeholder={`${HEIGHT_MIN}-${HEIGHT_MAX}`}
                />
                {layoutErrors[index]?.heightError && (
                  <div className="field-error">{layoutErrors[index].heightError}</div>
                )}
              </div>
              <button type="button" onClick={() => handleMoveUp(index)} disabled={index === 0}>
                ↑
              </button>
              <button type="button" onClick={() => handleMoveDown(index)} disabled={index === layout.length - 1}>
                ↓
              </button>
              <button type="button" onClick={() => handleRemoveChart(index)}>
                ✕
              </button>
              <label className="layout-checkbox-label">
                <input
                  type="checkbox"
                  checked={!!item.interpolateToLatest}
                  onChange={(e) => handleChartChange(index, 'interpolateToLatest', e.target.checked)}
                />
                Extend to now
              </label>
            </div>
          ))}
          <button type="button" onClick={handleAddChart}>
            + Add Chart
          </button>
        </div>
      </div>

      <div className="button-group">
        <button type="button" onClick={handleSave}>
          Save
        </button>
        <button type="button" onClick={() => onCopy(dashboard.id)}>
          Copy
        </button>
        <button type="button" onClick={handleDelete} className="btn-danger">
          Delete
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}
