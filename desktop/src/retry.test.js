import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  isTransientError,
  isNetworkError,
  computeDelay,
  fetchWithRetry,
  streamWithResilience,
} from "./retry";

describe("retry utilities", () => {
  describe("isTransientError", () => {
    it("returns true for 5xx status codes", () => {
      expect(isTransientError({ status: 500 })).toBe(true);
      expect(isTransientError({ status: 502 })).toBe(true);
      expect(isTransientError({ status: 503 })).toBe(true);
    });

    it("returns true for 408 and 429", () => {
      expect(isTransientError({ status: 408 })).toBe(true);
      expect(isTransientError({ status: 429 })).toBe(true);
    });

    it("returns false for success and client errors", () => {
      expect(isTransientError({ status: 200 })).toBe(false);
      expect(isTransientError({ status: 400 })).toBe(false);
      expect(isTransientError({ status: 404 })).toBe(false);
    });

    it("returns false for null/undefined", () => {
      expect(isTransientError(null)).toBe(false);
      expect(isTransientError(undefined)).toBe(false);
    });
  });

  describe("isNetworkError", () => {
    it("detects fetch failures", () => {
      expect(isNetworkError(new TypeError("Failed to fetch"))).toBe(true);
    });

    it("detects connection errors", () => {
      expect(isNetworkError(new Error("ECONNREFUSED"))).toBe(true);
      expect(isNetworkError(new Error("ECONNRESET"))).toBe(true);
    });

    it("detects timeout errors", () => {
      expect(isNetworkError(new Error("Request timeout"))).toBe(true);
    });

    it("returns false for non-network errors", () => {
      expect(isNetworkError(new Error("Invalid JSON"))).toBe(false);
      expect(isNetworkError(null)).toBe(false);
    });
  });

  describe("computeDelay", () => {
    it("returns exponential base with jitter", () => {
      vi.spyOn(Math, "random").mockReturnValue(0.5);
      expect(computeDelay(0)).toBe(1250);
      expect(computeDelay(1)).toBe(2250);
      expect(computeDelay(2)).toBe(4250);
      vi.restoreAllMocks();
    });
  });

  describe("fetchWithRetry", () => {
    beforeEach(() => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
    });

    afterEach(() => {
      vi.useRealTimers();
      vi.restoreAllMocks();
    });

    it("returns response on immediate success", async () => {
      const mockResponse = { status: 200, json: () => ({ ok: true }) };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse));

      const result = await fetchWithRetry("http://localhost/api");
      expect(result).toBe(mockResponse);
      expect(fetch).toHaveBeenCalledTimes(1);
    });

    it("retries on transient error then succeeds", async () => {
      const transientResponse = { status: 503 };
      const successResponse = { status: 200, json: () => ({ ok: true }) };
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValueOnce(transientResponse).mockResolvedValueOnce(successResponse),
      );
      vi.spyOn(Math, "random").mockReturnValue(0);

      const result = await fetchWithRetry("http://localhost/api", {}, { maxRetries: 2 });
      expect(result).toBe(successResponse);
      expect(fetch).toHaveBeenCalledTimes(2);
    });

    it("retries on network error then succeeds", async () => {
      const successResponse = { status: 200, json: () => ({ ok: true }) };
      vi.stubGlobal(
        "fetch",
        vi.fn()
          .mockRejectedValueOnce(new TypeError("Failed to fetch"))
          .mockResolvedValueOnce(successResponse),
      );
      vi.spyOn(Math, "random").mockReturnValue(0);

      const result = await fetchWithRetry("http://localhost/api", {}, { maxRetries: 2 });
      expect(result).toBe(successResponse);
      expect(fetch).toHaveBeenCalledTimes(2);
    });

    it("throws after exhausting retries", async () => {
      vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
      vi.spyOn(Math, "random").mockReturnValue(0);

      await expect(
        fetchWithRetry("http://localhost/api", {}, { maxRetries: 1 }),
      ).rejects.toThrow("Failed to fetch");
      expect(fetch).toHaveBeenCalledTimes(2);
    });

    it("does not retry non-transient client errors", async () => {
      const clientError = { status: 400 };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(clientError));

      const result = await fetchWithRetry("http://localhost/api", {}, { maxRetries: 3 });
      expect(result).toBe(clientError);
      expect(fetch).toHaveBeenCalledTimes(1);
    });
  });

  describe("streamWithResilience", () => {
    beforeEach(() => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
    });

    afterEach(() => {
      vi.useRealTimers();
      vi.restoreAllMocks();
    });

    it("returns response on success", async () => {
      const mockResponse = { ok: true, status: 200, body: {} };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse));

      const result = await streamWithResilience("http://localhost/stream", { message: "hi" });
      expect(result).toBe(mockResponse);
    });

    it("marks network errors as partial", async () => {
      vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Invalid JSON")));

      try {
        await streamWithResilience("http://localhost/stream", { message: "hi" }, {}, { maxRetries: 0 });
      } catch (error) {
        expect(error._streamPartial).toBe(true);
      }
    });
  });
});
