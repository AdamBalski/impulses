import { useMemo } from 'react';
import ReactApexChart from 'react-apexcharts';

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

export default function Plot({
  data = {},
  variables = [],
  width = 700,
  height = 300,
  formatYAsDurationMs = false,
  xRange = null,
  yRanges = { left: null, right: null },
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

    const series = variables.map(variable => {
      const variableName = variable.variable;
      const points = data[variableName] || [];
      if (points.length > 0) hasData = true;

      const sorted = [...points].sort((a, b) => a.timestamp ?? 0 - b.timestamp ?? 0);
      const displayType = variable.displayType || 'line';
      const apexSeriesType =
        displayType === 'dots' ? 'scatter' : displayType === 'bar' ? 'column' : 'line';

      return {
        name: variableName,
        data: sorted
          .map(p => {
            const x = p.timestamp;
            return x == null ? null : { x, y: p.value, dimensions: p.dimensions || {} };
          })
          .filter(Boolean),
        color: variable.color || '#0066cc',
        type: apexSeriesType,
      };
    });

    return { series, hasData };
  }, [data, variables]);

  const options = useMemo(() => {
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
        width: variables.map(i => {
          if (i.displayType === 'dots' || i.displayType === 'bar') {
            return 0;
          }
          return 2;
        }),
        curve: 'straight',
      },
      markers: {
        size: variables.map(i => (i.displayType === 'dots' ? 4 : 0)),
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

  if (!hasData) {
    return (
      <div className="chart-canvas chart-canvas--empty">
        <span className="chart-canvas__empty-text">No data available</span>
      </div>
    );
  }

  return (
    <div className="chart-canvas">
      <ReactApexChart options={options} series={series} type="line" width={width} height={height} />
    </div>
  );
}
