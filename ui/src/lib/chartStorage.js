const STORAGE_KEY = 'impulses_charts';

export function loadChartsFromStorage() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return {};
    const parsed = JSON.parse(stored);
    return typeof parsed === 'object' && parsed !== null ? parsed : {};
  } catch {
    return {};
  }
}

export function saveChartsToStorage(chartsMap) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(chartsMap));
}

export { STORAGE_KEY };
