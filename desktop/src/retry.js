export function isTransientError(response) {
  if (!response || typeof response.status !== "number") {
    return false;
  }
  if (response.status === 408 || response.status === 429) {
    return true;
  }
  return response.status >= 500;
}

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

export function computeDelay(attempt) {
  const base = 1000 * Math.pow(2, attempt);
  const jitter = Math.random() * 500;
  return base + jitter;
}

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
