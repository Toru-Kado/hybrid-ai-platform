const STORAGE_KEY = "tk-ai-text-prediction";

export function getTextPredictionEnabled() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw === null ? true : raw === "true";
  } catch (_error) {
    return true;
  }
}

export function storeTextPredictionEnabled(enabled) {
  try {
    localStorage.setItem(STORAGE_KEY, String(enabled));
  } catch (_error) {
    // localStorage unavailable
  }
}
