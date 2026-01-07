import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { compute, COMMON_LIBRARY } from '@impulses/sdk-typescript';
import Plot from './Plot';
import { getImpulsesClient } from '../lib/sdkClient';
import { DISPLAY_TYPE_DEFAULT, getDisplayTypeMeta } from '../lib/displayTypes';

function processSeriesData(rawData, variablesList, shouldCutFuture, shouldInterpolateToLatest) {
  const now = Date.now();
  let globalMaxTs = null;

  const processed = {};
  for (const variable of variablesList) {
    const name = variable.variable?.trim();
    if (!name) continue;
    let points = rawData[name] ?? [];

    if (shouldCutFuture) {
      points = points.filter(p => typeof p?.timestamp === 'number' && p.timestamp <= now);
    }

    for (const p of points) {
      if (typeof p?.timestamp === 'number') {
        if (globalMaxTs == null || p.timestamp > globalMaxTs) {
          globalMaxTs = p.timestamp;
        }
      }
    }

    processed[name] = points;
  }

  if (shouldInterpolateToLatest && globalMaxTs != null) {
    for (const variable of variablesList) {
      const name = variable.variable?.trim();
      if (!name) continue;
      const meta = getDisplayTypeMeta(variable.displayType);
      if (!meta.interpolatable) continue;

      const points = processed[name];
      if (!points || points.length === 0) continue;

      const sorted = [...points].sort((a, b) => (a.timestamp ?? 0) - (b.timestamp ?? 0));
      const lastPoint = sorted[sorted.length - 1];
      if (lastPoint && lastPoint.timestamp < globalMaxTs) {
        processed[name] = [...sorted, { ...lastPoint, timestamp: globalMaxTs }];
      }
    }
  }

  return processed;
}

const ZOOM_PRESETS = [
  { label: 'Y', durationMs: 365 * 24 * 60 * 60 * 1000 },
  { label: '6M', durationMs: 183 * 24 * 60 * 60 * 1000 },
  { label: '3M', durationMs: 92 * 24 * 60 * 60 * 1000 },
  { label: 'M', durationMs: 31 * 24 * 60 * 60 * 1000 },
  { label: 'W', durationMs: 7 * 24 * 60 * 60 * 1000 },
];

const DAY_MS = 24 * 60 * 60 * 1000;

function parseDuration(duration) {
  const regex = /(-?\d+)(d|h|min|ms|m|s)/g;
  let match;
  let total = 0;
  while ((match = regex.exec(duration)) !== null) {
    const amount = parseInt(match[1], 10);
    const unit = match[2];
    switch (unit) {
      case 'd':
        total += amount * DAY_MS;
        break;
      case 'h':
        total += amount * 60 * 60 * 1000;
        break;
      case 'min':
      case 'm':
        total += amount * 60 * 1000;
        break;
      case 's':
        total += amount * 1000;
        break;
      case 'ms':
        total += amount;
        break;
      default:
        break;
    }
  }
  return total;
}

function parseCustomWindow(input) {
  if (!input || !input.trim()) return null;
  const trimmed = input.trim();
  const now = Date.now();

  if (trimmed.includes(':')) {
    const [fromPart, toPart] = trimmed.split(':');
    const fromMs = parseDuration(fromPart.trim());
    const toMs = parseDuration(toPart.trim());
    return {
      start: now + fromMs,
      end: now + toMs,
    };
  }

  const durationMs = parseDuration(trimmed);
  if (durationMs < 0) {
    return {
      start: now + durationMs,
      end: now,
    };
  } else if (durationMs > 0) {
    return {
      start: now,
      end: now + durationMs,
    };
  }
  return null;
}

export default function Chart({
  chart,
  onUpdate,
  onDelete,
  fillParent = false,
  globalZoomCommand = null,
  interpolateToLatestOverride = null,
  dashboardSeriesData = null,
  dashboardDefaultZoomWindow = null,
  dashboardOverrideChartZoom = false,
}) {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [xRange, setXRange] = useState(null);
  const [yRanges, setYRanges] = useState({ left: null, right: null });
  const lastZoomCommandIdRef = useRef(null);
  const [customZoomInput, setCustomZoomInput] = useState('');
  const hasAppliedDefaultZoomRef = useRef(false);

  const shouldInterpolateToLatest =
    typeof interpolateToLatestOverride === 'boolean'
      ? interpolateToLatestOverride
      : !!chart.interpolateToLatest;

  const shouldCutFuture = !!chart.cutFutureDatapoints;

  const variables = useMemo(() => {
    let vars;
    if (Array.isArray(chart.variables) && chart.variables.length > 0) {
      vars = chart.variables.map((variable) => ({
        ...variable,
        displayType: variable.displayType || DISPLAY_TYPE_DEFAULT,
        useRightAxis: Boolean(variable.useRightAxis),
      }));
    } else {
      const legacy = Array.isArray(chart.impulses) ? chart.impulses : [];
      vars = legacy.map((impulse, idx) => ({
        variable: impulse?.impulse_expression || `series_${idx + 1}`,
        color: impulse?.color || '#0066cc',
        displayType: impulse?.displayType || DISPLAY_TYPE_DEFAULT,
        useRightAxis: false,
      }));
    }

    return {
      list: vars,
      shouldInterpolateToLatest,
      shouldCutFuture,
    };
  }, [chart.variables, chart.impulses, shouldInterpolateToLatest, shouldCutFuture]);

  const useDashboardData = dashboardSeriesData !== null;

  useEffect(() => {
    if (useDashboardData) {
      const rawData = {};
      for (const variable of variables.list) {
        const name = variable.variable?.trim();
        if (!name) continue;
        rawData[name] = dashboardSeriesData[name] || [];
      }
      const processed = processSeriesData(
        rawData,
        variables.list,
        variables.shouldCutFuture,
        variables.shouldInterpolateToLatest,
      );
      setData(processed);
      setXRange(null);
      setYRanges({ left: null, right: null });
      setError('');
      return;
    }

    if (chart.program && variables.list.length > 0) {
      loadData();
    }
  }, [chart.program, chart.updatedAt, variables, useDashboardData, dashboardSeriesData]);

  async function loadData() {
    if (useDashboardData) {
      return;
    }
    if (!chart.program) {
      setError('Missing PulseLang program');
      return;
    }
    if (variables.list.length === 0) {
      setError('Add at least one variable to render a chart');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const client = getImpulsesClient();
      const resultMap = await compute(client, COMMON_LIBRARY, chart.program);
      const nextData = {};

      for (const variable of variables.list) {
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

      const processed = processSeriesData(
        nextData,
        variables.list,
        variables.shouldCutFuture,
        variables.shouldInterpolateToLatest,
      );
      setData(processed);
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

  const getAxisBounds = useCallback((start, end, axis) => {
    let min = Infinity;
    let max = -Infinity;
    for (const variable of variables.list) {
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
  }, [variables.list, data]);

  const applyZoom = useCallback((durationMs) => {
    if (!timeBounds.max) {
      return false;
    }
    const end = timeBounds.max;
    const start = timeBounds.min != null ? Math.max(timeBounds.min, end - durationMs) : end - durationMs;
    setXRange({ min: start, max: end });
    setYRanges({
      left: getAxisBounds(start, end, 'left'),
      right: getAxisBounds(start, end, 'right'),
    });
    return true;
  }, [timeBounds, getAxisBounds]);

  const applyCustomZoom = useCallback((inputValue) => {
    const window = parseCustomWindow(inputValue);
    if (!window) return false;
    setXRange({ min: window.start, max: window.end });
    setYRanges({
      left: getAxisBounds(window.start, window.end, 'left'),
      right: getAxisBounds(window.start, window.end, 'right'),
    });
    return true;
  }, [getAxisBounds]);

  const handleCustomZoomKeyDown = useCallback((e) => {
    if (e.key === 'Enter') {
      applyCustomZoom(customZoomInput);
    }
  }, [applyCustomZoom, customZoomInput]);

  useEffect(() => {
    if (!globalZoomCommand) {
      return;
    }
    if (globalZoomCommand.id && globalZoomCommand.id === lastZoomCommandIdRef.current) {
      return;
    }
    if (globalZoomCommand.type === 'preset') {
      const applied = applyZoom(globalZoomCommand.durationMs);
      if (applied) {
        lastZoomCommandIdRef.current = globalZoomCommand.id;
      }
    } else if (globalZoomCommand.type === 'custom') {
      setXRange({ min: globalZoomCommand.start, max: globalZoomCommand.end });
      setYRanges({
        left: getAxisBounds(globalZoomCommand.start, globalZoomCommand.end, 'left'),
        right: getAxisBounds(globalZoomCommand.start, globalZoomCommand.end, 'right'),
      });
      lastZoomCommandIdRef.current = globalZoomCommand.id;
    } else if (globalZoomCommand.type === 'reset') {
      setXRange(null);
      setYRanges({ left: null, right: null });
      lastZoomCommandIdRef.current = globalZoomCommand.id;
    }
  }, [globalZoomCommand, timeBounds, applyZoom, getAxisBounds]);

  useEffect(() => {
    if (hasAppliedDefaultZoomRef.current) return;
    if (!timeBounds.max) return;

    let effectiveZoomWindow = null;
    if (dashboardDefaultZoomWindow && dashboardOverrideChartZoom) {
      effectiveZoomWindow = dashboardDefaultZoomWindow;
    } else if (chart.defaultZoomWindow) {
      effectiveZoomWindow = chart.defaultZoomWindow;
    } else if (dashboardDefaultZoomWindow) {
      effectiveZoomWindow = dashboardDefaultZoomWindow;
    }

    if (effectiveZoomWindow) {
      const applied = applyCustomZoom(effectiveZoomWindow);
      if (applied) {
        hasAppliedDefaultZoomRef.current = true;
      }
    }
  }, [timeBounds.max, chart.defaultZoomWindow, dashboardDefaultZoomWindow, dashboardOverrideChartZoom, applyCustomZoom]);

  const hasLeftAxis = variables.list.some(v => !v.useRightAxis);
  const hasRightAxis = variables.list.some(v => v.useRightAxis);
  const plotYRanges = useMemo(() => ({
    left: hasLeftAxis ? yRanges.left : null,
    right: hasRightAxis ? yRanges.right : null,
  }), [hasLeftAxis, hasRightAxis, yRanges.left, yRanges.right]);

  const containerClassName = fillParent
    ? 'chart-container chart-container--fill'
    : 'chart-container';
  const plotWrapperClassName = fillParent ? 'chart-plot-wrapper--fill' : undefined;
  const plotClassName = fillParent ? 'chart-plot--fill' : undefined;
  const plotHeight = fillParent ? '100%' : 300;

  return (
    <div className={containerClassName}>
      <div className="chart-header">
        <h4>{chart.name || 'Untitled Chart'}</h4>
        <div className="chart-actions">
          <div className="chart-zoom-buttons">
            {ZOOM_PRESETS.map((preset) => (
              <button
                key={preset.label}
                type="button"
                onClick={() => applyZoom(preset.durationMs)}
                disabled={!timeBounds.max}
              >
                {preset.label}
              </button>
            ))}
            <input
              type="text"
              className="custom-zoom-input"
              value={customZoomInput}
              onChange={(e) => setCustomZoomInput(e.target.value)}
              onKeyDown={handleCustomZoomKeyDown}
              placeholder="Custom"
            />
          </div>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      <div className={plotWrapperClassName}>
        <Plot
          data={data}
          variables={variables.list}
          width="100%"
          height={plotHeight}
          className={plotClassName}
          formatYAsDurationMs={!!chart.formatYAsDurationMs}
          xRange={xRange}
          yRanges={plotYRanges}
        />
      </div>

      <div className="chart-legend">
        {variables.list.map((variable, idx) => (
          <div key={idx} className="legend-item">
            <span className="legend-color" style={{ backgroundColor: variable.color || '#0066cc' }} />
            <span>
              {variable.alias?.trim() || variable.variable}
              {variable.useRightAxis ? ' (Right axis)' : ''}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
