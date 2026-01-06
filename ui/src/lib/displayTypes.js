export const DISPLAY_TYPE_DEFAULT = 'line';

const DISPLAY_TYPE_META = {
  line: {
    apexType: 'line',
    strokeWidth: 2,
    markerSize: 3,
    interpolatable: true,
  },
  dots: {
    apexType: 'scatter',
    strokeWidth: 0,
    markerSize: 4,
    interpolatable: false,
  },
  bar: {
    apexType: 'column',
    strokeWidth: 0,
    markerSize: 0,
    interpolatable: false,
  },
};

export function getDisplayTypeMeta(type = DISPLAY_TYPE_DEFAULT) {
  if (!type) {
    return DISPLAY_TYPE_META[DISPLAY_TYPE_DEFAULT];
  }
  return DISPLAY_TYPE_META[type] ?? DISPLAY_TYPE_META[DISPLAY_TYPE_DEFAULT];
}

export const DISPLAY_TYPE_OPTIONS = Object.keys(DISPLAY_TYPE_META);
