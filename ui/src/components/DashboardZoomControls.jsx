import { useState, useCallback } from 'react';

const PRESETS = [
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

export default function DashboardZoomControls({ onPreset, onReset, onCustomWindow }) {
  const [customInput, setCustomInput] = useState('');

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && onCustomWindow) {
      const window = parseCustomWindow(customInput);
      if (window) {
        onCustomWindow(window);
      }
    }
  }, [customInput, onCustomWindow]);

  return (
    <div className="dashboard-zoom-controls">
      <span>Zoom: </span>
      {PRESETS.map((preset) => (
        <button key={preset.label} type="button" onClick={() => onPreset(preset)}>
          {preset.label}
        </button>
      ))}
      <input
        type="text"
        className="custom-zoom-input"
        value={customInput}
        onChange={(e) => setCustomInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Custom"
      />
      <button type="button" onClick={onReset}>
        Reset
      </button>
    </div>
  );
}
