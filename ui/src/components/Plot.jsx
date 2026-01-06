import { useMemo } from 'react';
import ReactApexChart from 'react-apexcharts';
import { getDisplayTypeMeta } from '../lib/displayTypes';

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

function formatNumber(val) {
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

export default function Plot({
  data = {},
  variables = [],
  width = 700,
  height = 300,
  formatYAsDurationMs = false,
  xRange = null,
  yRanges = { left: null, right: null },
  interpolateToLatest = false,
  cutFutureDatapoints = false,
  style = {},
}) {
  const { hasLeftAxis, hasRightAxis, firstLeftName, firstRightName } = useMemo(() => {
    let firstLeft = null;
    let firstRight = null;
    for (const variable of variables) {
      if (!variable.useRightAxis && !firstLeft) {
        firstLeft = variable.variable;
      }
      if (variable.useRightAxis && !firstRight) {
        firstRight = variable.variable;
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
    let globalMaxTimestamp = null;
    const now = Date.now();

    const baseSeries = variables.map(variable => {
      const variableName = variable.variable;
      let points = data[variableName] || [];
      if (cutFutureDatapoints) {
        points = points.filter((point) => {
          if (typeof point?.timestamp !== 'number') {
            return false;
          }
          return point.timestamp <= now;
        });
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
          if (typeof x === 'number') {
            if (globalMaxTimestamp == null || x > globalMaxTimestamp) {
              globalMaxTimestamp = x;
            }
          }
          return x == null ? null : { x, y: p.value, dimensions: p.dimensions || {} };
        })
        .filter(Boolean);

      return {
        name: variableName,
        data: mapped,
        color: variable.color || '#0066cc',
        type: apexSeriesType,
      };
    });

    const targetMaxTimestamp = interpolateToLatest
      ? (typeof xRange?.max === 'number' ? xRange.max : globalMaxTimestamp)
      : null;

    const series = baseSeries.map((serie, idx) => {
      if (
        !interpolateToLatest ||
        !serie.data.length ||
        targetMaxTimestamp == null ||
        serie.data[serie.data.length - 1].x >= targetMaxTimestamp
      ) {
        return serie;
      }

      const variable = variables[idx];
      const meta = getDisplayTypeMeta(variable?.displayType);
      if (!meta.interpolatable) {
        return serie;
      }

      const lastPoint = serie.data[serie.data.length - 1];
      const extendedData = [
        ...serie.data,
        { ...lastPoint, x: targetMaxTimestamp },
      ];
      return { ...serie, data: extendedData };
    });

    return { series, hasData };
  }, [data, variables, interpolateToLatest, cutFutureDatapoints, xRange]);

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
        formatter: formatYAsDurationMs ? (val) => formatDurationMs(val) : (val) => formatNumber(val),
      },
      tickAmount: 8,
    }));

    if (yaxis.length === 0) {
      yaxis.push({
        seriesName: undefined,
        labels: {
          style: { fontSize: '10px' },
          formatter: formatYAsDurationMs ? (val) => formatDurationMs(val) : (val) => formatNumber(val),
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
          const yText = y == null ? 'N/A' : (formatYAsDurationMs ? formatDurationMs(y) : formatNumber(y));

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
  }, [formatYAsDurationMs, variables, xRange, yRanges, firstLeftName, firstRightName]);

  const computedWidth = toCssSize(width, '100%');
  const computedHeight = toCssSize(height, '300px');
  const containerStyle = { width: computedWidth, height: computedHeight, ...style };

  if (!hasData) {
    return (
      <div className="chart-canvas chart-canvas--empty" style={containerStyle}>
        <span className="chart-canvas__empty-text">No data available</span>
      </div>
    );
  }

  return (
    <div className="chart-canvas" style={containerStyle}>
      <ReactApexChart options={options} series={series} type="line" width="100%" height="100%" />
    </div>
  );
}
