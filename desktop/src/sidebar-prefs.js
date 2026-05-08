const STORAGE_KEY = "hybrid-ai-sidebar";

export function getStoredSidebarPrefs() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (_error) {
    return null;
  }
}

export function storeSidebarPrefs({ width, isOpen }) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ width, isOpen }));
  } catch (_error) {
    // localStorage unavailable
  }
}
