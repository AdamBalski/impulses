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

export default function Plot({ data = {}, impulses = [], width = 700, height = 300, formatYAsDurationMs = false }) {
  const { series, hasData } = useMemo(() => {
    let hasData = false;

    const series = impulses.map(impulse => {
      const points = data[impulse.impulse_expression] || [];
      if (points.length > 0) hasData = true;

      const sorted = [...points].sort((a, b) => a.timestamp ?? 0 - b.timestamp ?? 0);
      const displayType = impulse.displayType || 'line';

      return {
        name: impulse.impulse_expression,
        data: sorted
          .map(p => {
            const x = p.timestamp;
            return x == null ? null : { x, y: p.value };
          })
          .filter(Boolean),
        color: impulse.color || '#0066cc',
        type: displayType === 'dots' ? 'scatter' : 'line',
      };
    });

    return { series, hasData };
  }, [data, impulses]);

  const options = useMemo(() => {
    return {
      chart: {
        toolbar: { show: false },
        animations: { enabled: false },
      },
      stroke: {
        width: impulses.map(i => i.displayType === 'dots' ? 0 : 2),
        curve: 'straight',
      },
      markers: {
        size: impulses.map(i => i.displayType === 'dots' ? 4 : 0),
      },
      grid: {
        borderColor: '#ddd',
      },
      tooltip: {
        x: {
          format: 'MMM dd, HH:mm:ss',
        },
        y: formatYAsDurationMs
          ? {
              formatter: (val) => formatDurationMs(val),
            }
          : undefined,
      },
      xaxis: {
        type: 'datetime',
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
      yaxis: {
        labels: {
          style: { fontSize: '10px' },
          formatter: formatYAsDurationMs ? (val) => formatDurationMs(val) : undefined,
        },
      },
      legend: { show: false },
      colors: impulses.map(i => i.color || '#0066cc'),
    };
  }, [formatYAsDurationMs, impulses]);

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
