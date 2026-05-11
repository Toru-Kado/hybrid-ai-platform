/**
 * @file Theme persistence and application utilities.
 *
 * Manages a light/dark colour-scheme preference that persists to localStorage
 * and applies the chosen theme via a `data-theme` attribute on the document root.
 * Falls back to the OS-level `prefers-color-scheme` media query when no
 * explicit preference is stored.
 */

const STORAGE_KEY = "hybrid-ai-theme";

/**
 * Retrieves the user's stored theme preference from localStorage.
 * @returns {string|null} "light", "dark", or null if nothing stored.
 */
export function getStoredTheme() {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch (_error) {
    return null;
  }
}

/**
 * Persists the selected theme to localStorage.
 * @param {string} theme - "light" or "dark".
 */
export function storeTheme(theme) {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch (_error) {
    // localStorage unavailable
  }
}

/**
 * Resolves the effective theme to apply, considering the stored preference
 * and falling back to the OS preference via matchMedia.
 * @param {string|null} stored - The value from getStoredTheme().
 * @returns {"light"|"dark"} The resolved theme to use.
 */
export function getEffectiveTheme(stored) {
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  if (typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

/**
 * Applies the given theme by setting the `data-theme` attribute on <html>.
 * CSS custom properties in styles.css react to this attribute.
 * @param {string} theme - "light" or "dark".
 */
export function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
}

/**
 * One-shot initializer: reads, resolves, and applies the theme at app start.
 * @returns {{ stored: string|null, effective: "light"|"dark" }}
 */
export function initializeTheme() {
  const stored = getStoredTheme();
  const effective = getEffectiveTheme(stored);
  applyTheme(effective);
  return { stored, effective };
}
