import { describe, expect, it } from "vitest";

import {
  COMPACT_LAYOUT_MAX_WIDTH,
  DEFAULT_SIDEBAR_WIDTH,
  SIDEBAR_MAX_WIDTH,
  SIDEBAR_MIN_WIDTH,
  clampSidebarWidth,
  isCompactViewport,
} from "./layout";

describe("layout helpers", () => {
  it("clamps the sidebar width within supported bounds", () => {
    expect(clampSidebarWidth(SIDEBAR_MIN_WIDTH - 80)).toBe(SIDEBAR_MIN_WIDTH);
    expect(clampSidebarWidth(SIDEBAR_MAX_WIDTH + 120)).toBe(SIDEBAR_MAX_WIDTH);
    expect(clampSidebarWidth(333.7)).toBe(334);
  });

  it("falls back to the default width for invalid values", () => {
    expect(clampSidebarWidth(Number.NaN)).toBe(DEFAULT_SIDEBAR_WIDTH);
  });

  it("switches into compact mode below the breakpoint", () => {
    expect(isCompactViewport(COMPACT_LAYOUT_MAX_WIDTH - 1)).toBe(true);
    expect(isCompactViewport(COMPACT_LAYOUT_MAX_WIDTH)).toBe(false);
  });
});
