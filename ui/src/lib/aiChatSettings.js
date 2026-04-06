const STORAGE_KEY = 'impulses_ai_chat_settings_v1';

const DEFAULT_SETTINGS = {
  modelId: '',
};

export function loadAiChatSettings() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      return { ...DEFAULT_SETTINGS };
    }
    const parsed = JSON.parse(stored);
    return {
      ...DEFAULT_SETTINGS,
      ...(typeof parsed === 'object' && parsed !== null ? parsed : {}),
    };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export function saveAiChatSettings(settings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    modelId: settings.modelId || '',
  }));
}
