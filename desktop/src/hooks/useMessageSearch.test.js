import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import useMessageSearch from "./useMessageSearch";

const mockMessages = [
  { message_id: 1, content: "hello world", role: "user" },
  { message_id: 2, content: "goodbye world", role: "assistant" },
  { message_id: 3, content: "nothing special here", role: "user" },
];

describe("useMessageSearch", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.assistantApi = {
      searchMessages: vi.fn().mockResolvedValue({ results: [] }),
    };
  });

  afterEach(() => {
    vi.useRealTimers();
    delete window.assistantApi;
  });

  it("starts with search closed", () => {
    const { result } = renderHook(() =>
      useMessageSearch({ messages: mockMessages, activeSession: null })
    );
    expect(result.current.isSearchOpen).toBe(false);
    expect(result.current.searchQuery).toBe("");
  });

  it("opens search on Cmd+F", () => {
    const { result } = renderHook(() =>
      useMessageSearch({ messages: mockMessages, activeSession: null })
    );

    act(() => {
      window.dispatchEvent(
        new KeyboardEvent("keydown", { key: "f", metaKey: true })
      );
    });

    expect(result.current.isSearchOpen).toBe(true);
  });

  it("performs local search after debounce", async () => {
    const { result } = renderHook(() =>
      useMessageSearch({ messages: mockMessages, activeSession: null })
    );

    act(() => {
      result.current.setSearchQuery("world");
    });

    // Before debounce: no results yet
    expect(result.current.localResults).toHaveLength(0);

    // After debounce
    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    expect(result.current.localResults).toHaveLength(2);
    expect(result.current.localResults[0].messageId).toBe(1);
    expect(result.current.localResults[1].messageId).toBe(2);
  });

  it("returns empty results for non-matching query", async () => {
    const { result } = renderHook(() =>
      useMessageSearch({ messages: mockMessages, activeSession: null })
    );

    act(() => {
      result.current.setSearchQuery("xyznonexistent");
    });

    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    expect(result.current.localResults).toHaveLength(0);
  });

  it("navigates matches wrapping around", async () => {
    const { result } = renderHook(() =>
      useMessageSearch({ messages: mockMessages, activeSession: null })
    );

    act(() => {
      result.current.setSearchQuery("world");
    });
    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    expect(result.current.activeMatchIndex).toBe(0);

    act(() => {
      result.current.navigateMatch(1);
    });
    expect(result.current.activeMatchIndex).toBe(1);

    act(() => {
      result.current.navigateMatch(1);
    });
    // Wraps back to 0
    expect(result.current.activeMatchIndex).toBe(0);
  });

  it("navigates backwards wrapping around", async () => {
    const { result } = renderHook(() =>
      useMessageSearch({ messages: mockMessages, activeSession: null })
    );

    act(() => {
      result.current.setSearchQuery("world");
    });
    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    expect(result.current.activeMatchIndex).toBe(0);

    act(() => {
      result.current.navigateMatch(-1);
    });
    // Wraps to last
    expect(result.current.activeMatchIndex).toBe(1);
  });

  it("closes search and resets state", async () => {
    const { result } = renderHook(() =>
      useMessageSearch({ messages: mockMessages, activeSession: null })
    );

    act(() => {
      result.current.setIsSearchOpen(true);
      result.current.setSearchQuery("world");
    });
    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    expect(result.current.localResults.length).toBeGreaterThan(0);

    act(() => {
      result.current.closeSearch();
    });

    expect(result.current.isSearchOpen).toBe(false);
    expect(result.current.searchQuery).toBe("");
    expect(result.current.localResults).toHaveLength(0);
    expect(result.current.activeMatchIndex).toBe(0);
  });

  it("exposes highlightedMessageId for active match", async () => {
    const { result } = renderHook(() =>
      useMessageSearch({ messages: mockMessages, activeSession: null })
    );

    act(() => {
      result.current.setSearchQuery("world");
    });
    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    expect(result.current.highlightedMessageId).toBe(1);

    act(() => {
      result.current.navigateMatch(1);
    });
    expect(result.current.highlightedMessageId).toBe(2);
  });

  it("calls API for cross-session search", async () => {
    const mockApi = {
      searchMessages: vi.fn().mockResolvedValue({
        results: [{ message_id: 10, session_id: 5, content: "cross result" }],
      }),
    };
    window.assistantApi = mockApi;

    const { result } = renderHook(() =>
      useMessageSearch({ messages: mockMessages, activeSession: null })
    );

    act(() => {
      result.current.setSearchMode("all");
      result.current.setSearchQuery("cross");
    });

    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    // Need to wait for the async API call to resolve
    await act(async () => {
      await Promise.resolve();
    });

    expect(mockApi.searchMessages).toHaveBeenCalledWith("cross", {});
    expect(result.current.crossResults).toHaveLength(1);
  });
});
