import { useState, useEffect, useMemo } from 'react';
import { compute, COMMON_LIBRARY } from '@impulses/sdk-typescript';
import Plot from './Plot';
import { getImpulsesClient } from '../lib/sdkClient';

export default function Chart({ chart, onUpdate, onDelete }) {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [xRange, setXRange] = useState(null);
  const [yRanges, setYRanges] = useState({ left: null, right: null });

  const variables = useMemo(() => {
    if (Array.isArray(chart.variables) && chart.variables.length > 0) {
      return chart.variables.map((variable) => ({
        ...variable,
        useRightAxis: Boolean(variable.useRightAxis),
      }));
    }
    const legacy = Array.isArray(chart.impulses) ? chart.impulses : [];
    return legacy.map((impulse, idx) => ({
      variable: impulse?.impulse_expression || `series_${idx + 1}`,
      color: impulse?.color || '#0066cc',
      displayType: impulse?.displayType || 'line',
      useRightAxis: false,
    }));
  }, [chart.variables, chart.impulses]);

  useEffect(() => {
    if (chart.program && variables.length > 0) {
      loadData();
    }
  }, [chart.program, chart.updatedAt, variables.length]);

  async function loadData() {
    if (!chart.program) {
      setError('Missing PulseLang program');
      return;
    }
    if (variables.length === 0) {
      setError('Add at least one variable to render a chart');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const client = getImpulsesClient();
      const resultMap = await compute(client, COMMON_LIBRARY, chart.program);
      const nextData = {};

      for (const variable of variables) {
        const name = variable.variable?.trim();
        if (!name) {
          nextData[name || ''] = [];
          continue;
        }

        const series = resultMap.get(name);
        if (series && typeof series.toDTO === 'function') {
          nextData[name] = series.toDTO();
        } else {
          nextData[name] = [];
        }
      }

      setData(nextData);
      setXRange(null);
      setYRanges({ left: null, right: null });
    } catch (err) {
      console.error('Failed to load chart data', err);
      setError(err?.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }

  const timeBounds = useMemo(() => {
    const timestamps = Object.values(data)
      .flatMap(series => series ?? [])
      .map(point => point?.timestamp)
      .filter((ts) => typeof ts === 'number')
      .sort((a, b) => a - b);
    if (timestamps.length === 0) {
      return { min: null, max: null };
    }
    return { min: timestamps[0], max: timestamps[timestamps.length - 1] };
  }, [data]);

  const zoomPresets = [
    { label: 'Y', durationMs: 365 * 24 * 60 * 60 * 1000 },
    { label: '6M', durationMs: 183 * 24 * 60 * 60 * 1000 },
    { label: '3M', durationMs: 92 * 24 * 60 * 60 * 1000 },
    { label: 'M', durationMs: 31 * 24 * 60 * 60 * 1000 },
    { label: 'W', durationMs: 7 * 24 * 60 * 60 * 1000 },
  ];

  function getAxisBounds(start, end, axis) {
    let min = Infinity;
    let max = -Infinity;
    for (const variable of variables) {
      const targetAxis = variable.useRightAxis ? 'right' : 'left';
      if (targetAxis !== axis) {
        continue;
      }
      const series = data[variable.variable] ?? [];
      for (const point of series ?? []) {
        const ts = point?.timestamp;
        const val = point?.value;
        if (typeof ts !== 'number' || typeof val !== 'number') {
          continue;
        }
        if (ts >= start && ts <= end) {
          if (val < min) min = val;
          if (val > max) max = val;
        }
      }
    }
    if (min === Infinity || max === -Infinity) {
      return null;
    }
    if (min === max) {
      const pad = Math.abs(min) * 0.1 || 1;
      return { min: min - pad, max: max + pad };
    }
    return { min, max };
  }

  function applyZoom(durationMs) {
    if (!timeBounds.max) {
      return;
    }
    const end = Date.now();
    const start = timeBounds.min != null ? Math.max(timeBounds.min, end - durationMs) : end - durationMs;
    setXRange({ min: start, max: end });
    setYRanges({
      left: getAxisBounds(start, end, 'left'),
      right: getAxisBounds(start, end, 'right'),
    });
  }

  return (
    <div className="chart-container">
      <div className="chart-header">
        <h3>{chart.name || 'Untitled Chart'}</h3>
        <div className="chart-actions">
          <div style={{ display: 'flex', gap: '0.25rem', marginRight: '0.75rem' }}>
            {zoomPresets.map((preset) => (
              <button
                key={preset.label}
                type="button"
                onClick={() => applyZoom(preset.durationMs)}
                disabled={!timeBounds.max}
                style={{ padding: '0.25em 0.5em' }}
              >
                {preset.label}
              </button>
            ))}
          </div>
          <button onClick={loadData} disabled={loading}>
            {loading ? 'Loading...' : 'Refresh'}
          </button>
          <button onClick={() => onDelete(chart.id)}>Delete</button>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      <Plot
        data={data}
        variables={variables}
        formatYAsDurationMs={!!chart.formatYAsDurationMs}
        xRange={xRange}
        yRanges={{
          left: variables.some(v => !v.useRightAxis) ? yRanges.left : null,
          right: variables.some(v => v.useRightAxis) ? yRanges.right : null,
        }}
      />

      <div className="chart-legend">
        {variables.map((variable, idx) => (
          <div key={idx} className="legend-item">
            <span className="legend-color" style={{ backgroundColor: variable.color || '#0066cc' }} />
            <span>
              {variable.variable}
              {variable.useRightAxis ? ' (Right axis)' : ''}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
