export function normalizeChart(chart) {
  return {
    id: chart.id,
    name: chart.name || '',
    description: chart.description || '',
    program: chart.program || '',
    variables: Array.isArray(chart.variables) ? chart.variables : [],
    formatYAsDurationMs: !!chart.format_y_as_duration_ms,
    interpolateToLatest: !!chart.interpolate_to_latest,
    cutFutureDatapoints: !!chart.cut_future_datapoints,
    defaultZoomWindow: chart.default_zoom_window || null,
    createdAt: chart.created_at,
    updatedAt: chart.updated_at,
  };
}

function sortObjectKeysDeep(value) {
  if (Array.isArray(value)) {
    return value.map(sortObjectKeysDeep);
  }
  if (value && typeof value === 'object') {
    return Object.keys(value)
      .sort((left, right) => left.localeCompare(right))
      .reduce((result, key) => {
        result[key] = sortObjectKeysDeep(value[key]);
        return result;
      }, {});
  }
  return value;
}

export function normalizeDisplayChart(chart, fallbackUpdatedAt = Date.now()) {
  return {
    id: chart.id || null,
    chartDerivedFrom: chart.chartDerivedFrom || chart.chart_derived_from || null,
    name: chart.name || '',
    description: chart.description || '',
    program: chart.program || '',
    variables: Array.isArray(chart.variables)
      ? chart.variables.map((variable) => ({
        ...variable,
        displayType: variable.displayType || variable.display_type || 'line',
        rollUp: variable.rollUp || variable.roll_up || 'last',
        useRightAxis: typeof variable.useRightAxis === 'boolean'
          ? variable.useRightAxis
          : !!variable.use_right_axis,
      }))
      : [],
    formatYAsDurationMs: !!chart.formatYAsDurationMs || !!chart.format_y_as_duration_ms,
    interpolateToLatest: !!chart.interpolateToLatest || !!chart.interpolate_to_latest,
    cutFutureDatapoints: !!chart.cutFutureDatapoints || !!chart.cut_future_datapoints,
    defaultZoomWindow: chart.defaultZoomWindow || chart.default_zoom_window || null,
    createdAt: chart.createdAt || chart.created_at || fallbackUpdatedAt,
    updatedAt: chart.updatedAt || chart.updated_at || fallbackUpdatedAt,
  };
}

export function toDisplayChartMetadataPayload(chart) {
  const normalized = normalizeDisplayChart(chart);
  const payload = {
    name: normalized.name || '',
    description: normalized.description || '',
    program: normalized.program || '',
    variables: (Array.isArray(normalized.variables) ? normalized.variables : []).map((variable) => ({
      alias: variable.alias || null,
      color: variable.color || null,
      display_type: variable.displayType || 'line',
      resolution: variable.resolution || null,
      roll_up: variable.rollUp || 'last',
      use_right_axis: !!variable.useRightAxis,
      variable: variable.variable || '',
    })),
    format_y_as_duration_ms: !!normalized.formatYAsDurationMs,
    interpolate_to_latest: !!normalized.interpolateToLatest,
    cut_future_datapoints: !!normalized.cutFutureDatapoints,
    default_zoom_window: normalized.defaultZoomWindow || null,
  };

  if (normalized.chartDerivedFrom) {
    payload.chart_derived_from = normalized.chartDerivedFrom;
  }

  return sortObjectKeysDeep(payload);
}

export function toDisplayChartMetadataJson(chart) {
  return JSON.stringify(toDisplayChartMetadataPayload(chart), null, 2);
}

export function normalizeDashboard(dashboard) {
  return {
    id: dashboard.id,
    name: dashboard.name || '',
    description: dashboard.description || '',
    program: dashboard.program || '',
    defaultZoomWindow: dashboard.default_zoom_window || null,
    overrideChartZoom: !!dashboard.override_chart_zoom,
    layout: Array.isArray(dashboard.layout) ? dashboard.layout : [],
    createdAt: dashboard.created_at,
    updatedAt: dashboard.updated_at,
  };
}

export function toChartBody(chart) {
  return {
    name: chart.name || '',
    description: chart.description || '',
    program: chart.program || '',
    variables: (Array.isArray(chart.variables) ? chart.variables : [])
      .filter((variable) => variable.variable.trim())
      .map((variable) => ({
        ...variable,
        useRightAxis: !!variable.useRightAxis,
      })),
    format_y_as_duration_ms: !!chart.formatYAsDurationMs,
    interpolate_to_latest: !!chart.interpolateToLatest,
    cut_future_datapoints: !!chart.cutFutureDatapoints,
    default_zoom_window: chart.defaultZoomWindow?.trim() || null,
  };
}

export function toDashboardBody(dashboard) {
  return {
    name: dashboard.name || '',
    description: dashboard.description || '',
    program: dashboard.program || '',
    default_zoom_window: dashboard.defaultZoomWindow || null,
    override_chart_zoom: !!dashboard.overrideChartZoom,
    layout: Array.isArray(dashboard.layout) ? dashboard.layout : [],
  };
}
