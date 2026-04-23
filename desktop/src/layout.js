export const COMPACT_LAYOUT_MAX_WIDTH = 1080;
export const SIDEBAR_MIN_WIDTH = 260;
export const SIDEBAR_MAX_WIDTH = 420;
export const DEFAULT_SIDEBAR_WIDTH = 320;

export function clampSidebarWidth(width) {
  if (!Number.isFinite(width)) {
    return DEFAULT_SIDEBAR_WIDTH;
  }
  return Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, Math.round(width)));
}

export function isCompactViewport(width) {
  return Number.isFinite(width) && width < COMPACT_LAYOUT_MAX_WIDTH;
}

export function readCompactViewport() {
  if (typeof window === "undefined") {
    return false;
  }
  return isCompactViewport(window.innerWidth);
}
