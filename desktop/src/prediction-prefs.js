/**
 * @file Text-prediction preference persistence.
 *
 * Stores the user's opt-in/opt-out choice for inline text prediction
 * (ghost-text completions) to localStorage. Defaults to enabled when no
 * stored preference exists.
 */

const STORAGE_KEY = "tk-ai-text-prediction";

/**
 * Reads whether inline text prediction is enabled.
 * @returns {boolean} true if enabled (or no stored preference), false if explicitly disabled.
 */
export function getTextPredictionEnabled() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw === null ? true : raw === "true";
  } catch (_error) {
    return true;
  }
}

/**
 * Persists the text-prediction enabled/disabled state.
 * @param {boolean} enabled - Whether text prediction should be active.
 */
export function storeTextPredictionEnabled(enabled) {
  try {
    localStorage.setItem(STORAGE_KEY, String(enabled));
  } catch (_error) {
    // localStorage unavailable
  }
}
