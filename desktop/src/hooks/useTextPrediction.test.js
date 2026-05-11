import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import useTextPrediction from "./useTextPrediction";

describe("useTextPrediction", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.assistantApi = {
      complete: vi.fn().mockResolvedValue({ completion: "configure my AWS credentials?" }),
    };
  });

  afterEach(() => {
    vi.useRealTimers();
    delete window.assistantApi;
    localStorage.clear();
  });

  it("starts with empty suggestion", () => {
    const { result } = renderHook(() =>
      useTextPrediction({ prompt: "", isBusy: false })
    );
    expect(result.current.suggestion).toBe("");
  });

  it("fetches prediction after debounce when text is long enough", async () => {
    const { result, rerender } = renderHook(
      ({ prompt, isBusy }) => useTextPrediction({ prompt, isBusy }),
      { initialProps: { prompt: "", isBusy: false } }
    );

    rerender({ prompt: "How do I", isBusy: false });

    // Before debounce
    expect(result.current.suggestion).toBe("");
    expect(window.assistantApi.complete).not.toHaveBeenCalled();

    // After debounce
    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    expect(window.assistantApi.complete).toHaveBeenCalledWith({
      text: "How do I",
      max_tokens: 50,
    });
    expect(result.current.suggestion).toBe("configure my AWS credentials?");
  });

  it("does not fetch when text is shorter than 3 characters", async () => {
    const { result, rerender } = renderHook(
      ({ prompt, isBusy }) => useTextPrediction({ prompt, isBusy }),
      { initialProps: { prompt: "", isBusy: false } }
    );

    rerender({ prompt: "Hi", isBusy: false });

    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    expect(window.assistantApi.complete).not.toHaveBeenCalled();
    expect(result.current.suggestion).toBe("");
  });

  it("does not fetch when isBusy is true", async () => {
    const { result, rerender } = renderHook(
      ({ prompt, isBusy }) => useTextPrediction({ prompt, isBusy }),
      { initialProps: { prompt: "", isBusy: false } }
    );

    rerender({ prompt: "How do I", isBusy: true });

    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    expect(window.assistantApi.complete).not.toHaveBeenCalled();
    expect(result.current.suggestion).toBe("");
  });

  it("does not fetch when disabled", async () => {
    localStorage.setItem("tk-ai-text-prediction", "false");

    const { result, rerender } = renderHook(
      ({ prompt, isBusy }) => useTextPrediction({ prompt, isBusy }),
      { initialProps: { prompt: "", isBusy: false } }
    );

    rerender({ prompt: "How do I", isBusy: false });

    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    expect(window.assistantApi.complete).not.toHaveBeenCalled();
    expect(result.current.suggestion).toBe("");
  });

  it("clears suggestion when prompt changes", async () => {
    const { result, rerender } = renderHook(
      ({ prompt, isBusy }) => useTextPrediction({ prompt, isBusy }),
      { initialProps: { prompt: "How do I", isBusy: false } }
    );

    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    expect(result.current.suggestion).toBe("configure my AWS credentials?");

    rerender({ prompt: "How do I c", isBusy: false });

    expect(result.current.suggestion).toBe("");
  });

  it("acceptFull returns full suggestion and clears it", async () => {
    const { result, rerender } = renderHook(
      ({ prompt, isBusy }) => useTextPrediction({ prompt, isBusy }),
      { initialProps: { prompt: "How do I", isBusy: false } }
    );

    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    let accepted;
    act(() => {
      accepted = result.current.acceptFull();
    });

    expect(accepted).toBe("configure my AWS credentials?");
    expect(result.current.suggestion).toBe("");
  });

  it("acceptWord returns first word and keeps remainder", async () => {
    const { result, rerender } = renderHook(
      ({ prompt, isBusy }) => useTextPrediction({ prompt, isBusy }),
      { initialProps: { prompt: "How do I", isBusy: false } }
    );

    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    let word;
    act(() => {
      word = result.current.acceptWord();
    });

    expect(word).toBe("configure");
    expect(result.current.suggestion).toBe(" my AWS credentials?");
  });

  it("dismiss clears the suggestion", async () => {
    const { result, rerender } = renderHook(
      ({ prompt, isBusy }) => useTextPrediction({ prompt, isBusy }),
      { initialProps: { prompt: "How do I", isBusy: false } }
    );

    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    expect(result.current.suggestion).toBe("configure my AWS credentials?");

    act(() => {
      result.current.dismiss();
    });

    expect(result.current.suggestion).toBe("");
  });

  it("cancels stale requests when prompt changes rapidly", async () => {
    let resolvers = [];
    window.assistantApi.complete = vi.fn().mockImplementation(
      ({ text }) =>
        new Promise((resolve) => {
          resolvers.push(() => resolve({ completion: `completion for: ${text}` }));
        })
    );

    const { result, rerender } = renderHook(
      ({ prompt, isBusy }) => useTextPrediction({ prompt, isBusy }),
      { initialProps: { prompt: "", isBusy: false } }
    );

    // Type first version, wait for debounce to fire request
    rerender({ prompt: "How", isBusy: false });
    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    // First request is now in flight — type more to trigger cancellation
    rerender({ prompt: "How do I", isBusy: false });
    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    // Both requests are pending; resolve the first (stale) one
    await act(async () => {
      resolvers[0]();
    });

    // Stale result should be ignored
    expect(result.current.suggestion).toBe("");

    // Resolve the second (latest) one
    await act(async () => {
      resolvers[1]();
    });

    expect(result.current.suggestion).toBe("completion for: How do I");
  });

  it("setIsEnabled persists preference and clears suggestion", async () => {
    const { result, rerender } = renderHook(
      ({ prompt, isBusy }) => useTextPrediction({ prompt, isBusy }),
      { initialProps: { prompt: "How do I", isBusy: false } }
    );

    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    expect(result.current.suggestion).toBe("configure my AWS credentials?");

    act(() => {
      result.current.setIsEnabled(false);
    });

    expect(result.current.isEnabled).toBe(false);
    expect(result.current.suggestion).toBe("");
    expect(localStorage.getItem("tk-ai-text-prediction")).toBe("false");
  });

  it("silently handles API errors", async () => {
    window.assistantApi.complete = vi.fn().mockRejectedValue(new Error("network error"));

    const { result, rerender } = renderHook(
      ({ prompt, isBusy }) => useTextPrediction({ prompt, isBusy }),
      { initialProps: { prompt: "How do I", isBusy: false } }
    );

    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    expect(result.current.suggestion).toBe("");
  });
});
