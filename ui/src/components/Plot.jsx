import { useMemo } from 'react';
import ReactApexChart from 'react-apexcharts';
import { getDisplayTypeMeta } from '../lib/displayTypes';
import { useUserSettings } from '../contexts/UserSettingsContext';

function formatDurationMs(ms) {
  if (ms == null || Number.isNaN(ms)) return '';
  const sign = ms < 0 ? '-' : '';
  const abs = Math.abs(ms);
  const totalSeconds = Math.floor(abs / 1000);
  const milliseconds = Math.floor(abs % 1000);
  const seconds = totalSeconds % 60;
  const totalMinutes = Math.floor(totalSeconds / 60);
  const minutes = totalMinutes % 60;
  const hours = Math.floor(totalMinutes / 60);

  const parts = [];
  if (hours) parts.push(`${hours}h`);
  if (minutes) parts.push(`${minutes}m`);
  if (seconds) parts.push(`${seconds}s`);
  if (milliseconds) parts.push(`${milliseconds}ms`);

  if (parts.length === 0) return '0ms';
  return sign + parts.join(' ');
}

function formatNumber(val, hideSensitiveData = false) {
  if (hideSensitiveData) {
    return 'Sensitive data';
  }
  if (val == null || Number.isNaN(val)) {
    return '';
  }
  const abs = Math.abs(val);
  if ((abs >= 1_000_000_000 || abs < 0.01) && abs != 0) {
    return val.toExponential(2);
  }
  return Number(val.toFixed(6)).toString();
}

function toCssSize(value, fallback) {
  if (value == null) return fallback;
  if (typeof value === 'number') {
    return `${value}px`;
  }
  return value;
}

const RESOLUTION_DURATIONS = {
  raw: null,
  day: 24 * 60 * 60 * 1000,
  week: 7 * 24 * 60 * 60 * 1000,
  two_weeks: 14 * 24 * 60 * 60 * 1000,
  month: 30 * 24 * 60 * 60 * 1000,
};

function applyResolutionAndRollUp(points, resolution, rollUp) {
  const bucketMs = RESOLUTION_DURATIONS[resolution];
  if (!bucketMs || points.length === 0) {
    return points;
  }

  const buckets = new Map();
  for (const point of points) {
    const ts = point.timestamp;
    if (typeof ts !== 'number') continue;
    const bucketKey = Math.floor(ts / bucketMs);
    if (!buckets.has(bucketKey)) {
      buckets.set(bucketKey, []);
    }
    buckets.get(bucketKey).push(point);
  }

  const result = [];
  for (const [bucketKey, bucketPoints] of buckets) {
    if (bucketPoints.length === 0) continue;

    const sorted = bucketPoints.sort((a, b) => (a.timestamp ?? 0) - (b.timestamp ?? 0));
    let aggregatedValue;
    let representativePoint;

    switch (rollUp) {
      case 'sum':
        aggregatedValue = sorted.reduce((sum, p) => sum + (p.value ?? 0), 0);
        representativePoint = sorted[sorted.length - 1];
        break;
      case 'average':
        aggregatedValue = sorted.reduce((sum, p) => sum + (p.value ?? 0), 0) / sorted.length;
        representativePoint = sorted[sorted.length - 1];
        break;
      case 'min':
        aggregatedValue = Math.min(...sorted.map(p => p.value ?? Infinity));
        representativePoint = sorted.find(p => p.value === aggregatedValue) || sorted[0];
        break;
      case 'max':
        aggregatedValue = Math.max(...sorted.map(p => p.value ?? -Infinity));
        representativePoint = sorted.find(p => p.value === aggregatedValue) || sorted[0];
        break;
      case 'last':
      default:
        representativePoint = sorted[sorted.length - 1];
        aggregatedValue = representativePoint.value;
        break;
    }

    result.push({
      ...representativePoint,
      value: aggregatedValue,
    });
  }

  return result.sort((a, b) => (a.timestamp ?? 0) - (b.timestamp ?? 0));
}

export default function Plot({
  data = {},
  variables = [],
  width = 700,
  height = 300,
  formatYAsDurationMs = false,
  xRange = null,
  yRanges = { left: null, right: null },
  className = '',
}) {
  const { hideSensitiveData } = useUserSettings();
  const { hasLeftAxis, hasRightAxis, firstLeftName, firstRightName } = useMemo(() => {
    let firstLeft = null;
    let firstRight = null;
    for (const variable of variables) {
      const displayName = variable.alias?.trim() || variable.variable;
      if (!variable.useRightAxis && !firstLeft) {
        firstLeft = displayName;
      }
      if (variable.useRightAxis && !firstRight) {
        firstRight = displayName;
      }
      if (firstLeft && firstRight) {
        break;
      }
    }
    return {
      hasLeftAxis: firstLeft != null,
      hasRightAxis: firstRight != null,
      firstLeftName: firstLeft || undefined,
      firstRightName: firstRight || undefined,
    };
  }, [variables]);

  const { series, hasData } = useMemo(() => {
    let hasData = false;

    const series = variables.map(variable => {
      const variableName = variable.variable;
      const displayName = variable.alias?.trim() || variableName;
      let points = data[variableName] || [];

      const resolution = variable.resolution || 'raw';
      const rollUp = variable.rollUp || 'last';
      if (resolution !== 'raw') {
        points = applyResolutionAndRollUp(points, resolution, rollUp);
      }

      if (points.length > 0) hasData = true;

      const sorted = [...points].sort(
        (a, b) => (a.timestamp ?? 0) - (b.timestamp ?? 0),
      );
      const typeMeta = getDisplayTypeMeta(variable.displayType);
      const apexSeriesType = typeMeta.apexType;

      const mapped = sorted
        .map(p => {
          const x = p.timestamp;
          return x == null ? null : { x, y: p.value, dimensions: p.dimensions || {} };
        })
        .filter(Boolean);

      return {
        name: displayName,
        data: mapped,
        color: variable.color || '#0066cc',
        type: apexSeriesType,
      };
    });

    return { series, hasData };
  }, [data, variables]);

  const valueFormatter = useMemo(() => {
    if (hideSensitiveData) {
      return () => ':|';
    }
    if (formatYAsDurationMs) {
      return (val) => formatDurationMs(val);
    }
    return (val) => formatNumber(val, false);
  }, [hideSensitiveData, formatYAsDurationMs]);

  const options = useMemo(() => {
    const displayMetas = variables.map((variable) => getDisplayTypeMeta(variable.displayType));

    const yaxis = variables.map((variable) => ({
      seriesName: variable.useRightAxis ? firstRightName : firstLeftName,
      min: variable.useRightAxis
        ? yRanges?.right?.min ?? undefined
        : yRanges?.left?.min ?? undefined,
      max: variable.useRightAxis
        ? yRanges?.right?.max ?? undefined
        : yRanges?.left?.max ?? undefined,
      opposite: !!variable.useRightAxis,
      labels: {
        style: { fontSize: '10px' },
        formatter: valueFormatter,
      },
      tickAmount: 8,
    }));

    if (yaxis.length === 0) {
      yaxis.push({
        seriesName: undefined,
        labels: {
          style: { fontSize: '10px' },
          formatter: valueFormatter,
        },
        tickAmount: 8,
      });
    }

    return {
      chart: {
        toolbar: { show: true },
        zoom: { enabled: true, type: 'xy' },
        animations: { enabled: false },
      },
      stroke: {
        width: displayMetas.map((meta) => meta.strokeWidth),
        curve: 'straight',
      },
      markers: {
        size: displayMetas.map((meta) => meta.markerSize),
        hover: {
          sizeOffset: 2,
        },
        strokeColors: 'transparent',
      },
      plotOptions: {
        bar: {
          columnWidth: '60%',
        },
      },
      grid: {
        borderColor: '#ddd',
      },
      tooltip: {
        shared: false,
        intersect: true,
        followCursor: true,
        custom: ({ series, seriesIndex, dataPointIndex, w }) => {
          const s = w?.config?.series?.[seriesIndex];
          const point = s?.data?.[dataPointIndex];
          const x = point?.x;
          const y = point?.y;
          const dims = point?.dimensions || {};

          const xText = x == null ? 'N/A' : new Date(x).toLocaleString();
          const yText = y == null ? 'N/A' : valueFormatter(y);

          const dimKeys = Object.keys(dims);
          const dimsHtml = dimKeys.length
            ? dimKeys
                .sort()
                .map(k => `<div><span style="opacity:0.75">${k}</span>: ${String(dims[k])}</div>`)
                .join('')
            : '<div style="opacity:0.75">No dimensions</div>';

          return `
            <div style="padding:8px 10px">
              <div style="font-weight:600; margin-bottom:4px">${s?.name || ''}</div>
              <div><span style="opacity:0.75">Time</span>: ${xText}</div>
              <div><span style="opacity:0.75">Value</span>: ${yText}</div>
              <div style="margin-top:6px">${dimsHtml}</div>
            </div>
          `;
        },
      },
      xaxis: {
        type: 'datetime',
        min: xRange?.min ?? undefined,
        max: xRange?.max ?? undefined,
        tooltip: {
          enabled: false,
        },
        labels: {
          style: { fontSize: '9px' },
          datetimeFormatter: {
            year: 'yyyy',
            month: "MMM 'yy",
            day: 'MMM dd',
            hour: 'HH:mm',
            minute: 'HH:mm',
            second: 'HH:mm:ss',
          },
        },
      },
      yaxis,
      legend: { show: false },
      colors: variables.map(i => i.color || '#0066cc'),
    };
  }, [formatYAsDurationMs, variables, xRange, yRanges, firstLeftName, firstRightName, valueFormatter]);

  const computedWidth = toCssSize(width, '100%');
  const computedHeight = toCssSize(height, '300px');
  const containerStyle = { width: computedWidth, height: computedHeight };
  const containerClass = className
    ? `chart-canvas ${className}`
    : 'chart-canvas';
  const emptyContainerClass = className
    ? `chart-canvas chart-canvas--empty ${className}`
    : 'chart-canvas chart-canvas--empty';

  if (!hasData) {
    return (
      <div className={emptyContainerClass} style={containerStyle}>
        <span className="chart-canvas__empty-text">No data available</span>
      </div>
    );
  }

  return (
    <div className={containerClass} style={containerStyle}>
      <ReactApexChart options={options} series={series} type="line" width="100%" height="100%" />
    </div>
  );
}
