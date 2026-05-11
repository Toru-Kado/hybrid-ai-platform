/**
 * @file Responsive layout constants and helpers.
 *
 * Provides breakpoint detection for the compact (mobile-like) vs. desktop
 * layout mode, and sidebar width clamping utilities used during drag-resize.
 */

/** Viewports narrower than this threshold use the compact (single-column) layout. */
export const COMPACT_LAYOUT_MAX_WIDTH = 1080;
/** Minimum allowed sidebar panel width in pixels during drag-resize. */
export const SIDEBAR_MIN_WIDTH = 260;
/** Maximum allowed sidebar panel width in pixels during drag-resize. */
export const SIDEBAR_MAX_WIDTH = 520;
/** Default sidebar width used on first launch before any user resizing. */
export const DEFAULT_SIDEBAR_WIDTH = 340;

/**
 * Clamps a sidebar width value to the allowed min/max range.
 * Returns the default width if the input is not a finite number.
 * @param {number} width - Desired sidebar width in pixels.
 * @returns {number} Clamped width within [SIDEBAR_MIN_WIDTH, SIDEBAR_MAX_WIDTH].
 */
export function clampSidebarWidth(width) {
  if (!Number.isFinite(width)) {
    return DEFAULT_SIDEBAR_WIDTH;
  }
  return Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, Math.round(width)));
}

/**
 * Determines whether a given viewport width qualifies as "compact" (mobile).
 * @param {number} width - Viewport width in pixels.
 * @returns {boolean} true if the viewport is below the compact breakpoint.
 */
export function isCompactViewport(width) {
  return Number.isFinite(width) && width < COMPACT_LAYOUT_MAX_WIDTH;
}

/**
 * Reads the current window width and returns whether the app should use
 * compact layout. Safe for SSR (returns false when window is undefined).
 * @returns {boolean}
 */
export function readCompactViewport() {
  if (typeof window === "undefined") {
    return false;
  }
  return isCompactViewport(window.innerWidth);
}
