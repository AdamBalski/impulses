import { useMemo } from 'react';

const PRESETS = [
  { label: 'Y', durationMs: 365 * 24 * 60 * 60 * 1000 },
  { label: '6M', durationMs: 183 * 24 * 60 * 60 * 1000 },
  { label: '3M', durationMs: 92 * 24 * 60 * 60 * 1000 },
  { label: 'M', durationMs: 31 * 24 * 60 * 60 * 1000 },
  { label: 'W', durationMs: 7 * 24 * 60 * 60 * 1000 },
];

export default function DashboardZoomControls({ onPreset, onReset }) {
  const buttons = useMemo(() => PRESETS, []);

  return (
    <div className="dashboard-zoom-controls">
      <span>Zoom: </span>
      {buttons.map((preset) => (
        <button key={preset.label} type="button" onClick={() => onPreset(preset)}>
          {preset.label}
        </button>
      ))}
      <button type="button" onClick={onReset}>
        Reset
      </button>
    </div>
  );
}
