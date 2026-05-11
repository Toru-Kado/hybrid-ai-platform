import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getEffectiveTheme, getStoredTheme, storeTheme, applyTheme, initializeTheme } from "./theme";

describe("theme utilities", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns null when no theme is stored", () => {
    expect(getStoredTheme()).toBeNull();
  });

  it("stores and retrieves a theme preference", () => {
    storeTheme("dark");
    expect(getStoredTheme()).toBe("dark");
    storeTheme("light");
    expect(getStoredTheme()).toBe("light");
  });

  it("resolves effective theme to light when no preference and no system dark mode", () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: false });
    expect(getEffectiveTheme(null)).toBe("light");
  });

  it("resolves effective theme to dark when system prefers dark", () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: true });
    expect(getEffectiveTheme(null)).toBe("dark");
  });

  it("respects stored preference over system preference", () => {
    window.matchMedia = vi.fn().mockReturnValue({ matches: true });
    expect(getEffectiveTheme("light")).toBe("light");
    expect(getEffectiveTheme("dark")).toBe("dark");
  });

  it("applies theme to document element", () => {
    applyTheme("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    applyTheme("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("initializes theme from stored preference", () => {
    storeTheme("dark");
    const result = initializeTheme();
    expect(result.effective).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });
});
