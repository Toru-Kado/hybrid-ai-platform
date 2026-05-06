const STORAGE_KEY = "hybrid-ai-theme";

export function getStoredTheme() {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch (_error) {
    return null;
  }
}

export function storeTheme(theme) {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch (_error) {
    // localStorage unavailable
  }
}

export function getEffectiveTheme(stored) {
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  if (typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

export function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
}

export function initializeTheme() {
  const stored = getStoredTheme();
  const effective = getEffectiveTheme(stored);
  applyTheme(effective);
  return { stored, effective };
}
