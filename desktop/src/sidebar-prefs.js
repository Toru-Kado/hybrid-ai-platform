/**
 * @file Sidebar preference persistence.
 *
 * Stores and retrieves the user's sidebar state (width and open/closed)
 * via localStorage so the layout is remembered across app restarts.
 */

const STORAGE_KEY = "hybrid-ai-sidebar";

/**
 * Reads persisted sidebar preferences from localStorage.
 * @returns {{ width: number, isOpen: boolean }|null} Stored prefs or null if unavailable.
 */
export function getStoredSidebarPrefs() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (_error) {
    return null;
  }
}

/**
 * Persists current sidebar preferences to localStorage.
 * @param {{ width: number, isOpen: boolean }} prefs - Sidebar state to save.
 */
export function storeSidebarPrefs({ width, isOpen }) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ width, isOpen }));
  } catch (_error) {
    // localStorage unavailable
  }
}
