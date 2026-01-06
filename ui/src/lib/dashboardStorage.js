const STORAGE_KEY = 'impulses-dashboards';

export function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

export function loadDashboardsFromStorage() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return {};
    const parsed = JSON.parse(stored);
    return typeof parsed === 'object' && parsed !== null ? parsed : {};
  } catch {
    return {};
  }
}

export function saveDashboardsToStorage(dashboardsMap) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(dashboardsMap));
}

export function createDashboard(name = 'Unnamed', description = '', layout = []) {
  const id = generateId();
  return {
    id,
    name,
    description,
    layout,
  };
}

export function getDashboard(id) {
  const dashboards = loadDashboardsFromStorage();
  return dashboards[id] || null;
}

export function saveDashboard(dashboard) {
  const dashboards = loadDashboardsFromStorage();
  dashboards[dashboard.id] = dashboard;
  saveDashboardsToStorage(dashboards);
  return dashboard;
}

export function deleteDashboard(id) {
  const dashboards = loadDashboardsFromStorage();
  delete dashboards[id];
  saveDashboardsToStorage(dashboards);
}

export function copyDashboard(id) {
  const dashboards = loadDashboardsFromStorage();
  const original = dashboards[id];
  if (!original) return null;
  
  const newDashboard = {
    ...original,
    id: generateId(),
    name: `${original.name} (copy)`,
  };
  dashboards[newDashboard.id] = newDashboard;
  saveDashboardsToStorage(dashboards);
  return newDashboard;
}

export { STORAGE_KEY };
