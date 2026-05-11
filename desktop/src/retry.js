/**
 * @file Retry and resilience utilities for HTTP requests.
 *
 * Provides exponential-backoff retry logic for both standard fetch calls and
 * streaming connections. Transient errors (5xx, 408, 429) and network failures
 * are retried automatically; non-retriable errors propagate immediately.
 */

/**
 * Determines whether an HTTP response status indicates a transient/retriable error.
 * Covers timeout (408), rate-limit (429), and server errors (5xx).
 * @param {Response} response - The fetch Response object.
 * @returns {boolean} true if the error is likely transient and worth retrying.
 */
export function isTransientError(response) {
  if (!response || typeof response.status !== "number") {
    return false;
  }
  if (response.status === 408 || response.status === 429) {
    return true;
  }
  return response.status >= 500;
}

/**
 * Checks whether an error represents a network-level failure (connection
 * refused, timeout, offline, etc.) as opposed to an application-level error.
 * @param {Error} error - The caught error.
 * @returns {boolean} true if the error appears to be network-related.
 */
export function isNetworkError(error) {
  if (!error) {
    return false;
  }
  const message = (error.message || "").toLowerCase();
  return (
    message.includes("failed to fetch") ||
    message.includes("network") ||
    message.includes("econnrefused") ||
    message.includes("econnreset") ||
    message.includes("timeout") ||
    error.name === "TypeError"
  );
}

/**
 * Computes the delay before the next retry using exponential backoff with jitter.
 * @param {number} attempt - Zero-based attempt index (0 = first retry).
 * @returns {number} Delay in milliseconds.
 */
export function computeDelay(attempt) {
  const base = 1000 * Math.pow(2, attempt);
  const jitter = Math.random() * 500;
  return base + jitter;
}

/**
 * Wraps the Fetch API with automatic retry on transient/network errors.
 * Returns the Response on success (even non-2xx that is not transient).
 * @param {string} url - Request URL.
 * @param {RequestInit} [options] - Standard fetch options.
 * @param {{ maxRetries?: number }} [retryOptions] - Retry configuration (default 3).
 * @returns {Promise<Response>} The final fetch Response.
 */
export async function fetchWithRetry(url, options = {}, retryOptions = {}) {
  const maxRetries = retryOptions.maxRetries ?? 3;

  let lastError = null;
  for (let attempt = 0; attempt <= maxRetries; attempt += 1) {
    try {
      const response = await fetch(url, options);
      if (isTransientError(response) && attempt < maxRetries) {
        await new Promise((resolve) => setTimeout(resolve, computeDelay(attempt)));
        continue;
      }
      return response;
    } catch (error) {
      lastError = error;
      if (isNetworkError(error) && attempt < maxRetries) {
        await new Promise((resolve) => setTimeout(resolve, computeDelay(attempt)));
        continue;
      }
      throw error;
    }
  }
  throw lastError;
}

/**
 * Initiates a streaming POST request with retry on transient/network errors.
 * On non-retriable failure, attaches `_streamPartial = true` to the error so
 * callers can distinguish mid-stream failures from pre-connection errors.
 * @param {string} url - Streaming endpoint URL.
 * @param {object} payload - JSON body to POST.
 * @param {object} [handlers] - Event handlers (unused here; passed through by callers).
 * @param {{ maxRetries?: number }} [options] - Retry configuration (default 2).
 * @returns {Promise<Response>} The successful Response ready for stream reading.
 */
export async function streamWithResilience(url, payload, handlers = {}, options = {}) {
  const maxRetries = options.maxRetries ?? 2;
  let attempt = 0;
  let lastError = null;

  while (attempt <= maxRetries) {
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (isTransientError(response) && attempt < maxRetries) {
        attempt += 1;
        await new Promise((resolve) => setTimeout(resolve, computeDelay(attempt - 1)));
        continue;
      }

      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.error || "Assistant request failed.");
      }

      return response;
    } catch (error) {
      lastError = error;
      if (isNetworkError(error) && attempt < maxRetries) {
        attempt += 1;
        await new Promise((resolve) => setTimeout(resolve, computeDelay(attempt - 1)));
        continue;
      }
      error._streamPartial = true;
      throw error;
    }
  }

  if (lastError) {
    lastError._streamPartial = true;
  }
  throw lastError;
}
