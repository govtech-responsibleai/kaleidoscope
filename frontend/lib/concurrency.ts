/**
 * Client-side concurrency helpers.
 *
 * Mirror of the backend `gather_with_concurrency`: bound how many async
 * operations run at once so a large evaluation does not fan out hundreds of
 * simultaneous requests (which overwhelmed the backend connection pool and
 * tripped 503s). Also provides a small retry-with-backoff for transient GETs.
 */

/**
 * Run `fn` over each item with at most `limit` operations in flight at a time.
 * Results are returned in the same order as the input items.
 */
export async function mapWithConcurrency<T, R>(
  items: readonly T[],
  limit: number,
  fn: (item: T, index: number) => Promise<R>,
): Promise<R[]> {
  const results: R[] = new Array(items.length);
  if (items.length === 0) return results;

  const effectiveLimit = Math.max(1, Math.min(limit, items.length));
  let nextIndex = 0;

  const worker = async (): Promise<void> => {
    while (true) {
      const current = nextIndex++;
      if (current >= items.length) return;
      results[current] = await fn(items[current], current);
    }
  };

  await Promise.all(Array.from({ length: effectiveLimit }, () => worker()));
  return results;
}

/** Sleep helper for backoff. */
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Retry an idempotent async operation on transient failures.
 *
 * Retries on network errors and 5xx responses only; never on 4xx (a 401/404 is
 * not going to succeed on retry). Uses exponential backoff (base * 2^attempt).
 *
 * @param fn        The operation to run.
 * @param attempts  Total attempts including the first (default 3).
 * @param baseMs    Base backoff delay in ms (default 300).
 */
export async function retryTransient<R>(
  fn: () => Promise<R>,
  attempts = 3,
  baseMs = 300,
): Promise<R> {
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      if (!isTransientError(err) || attempt === attempts - 1) {
        throw err;
      }
      await delay(baseMs * 2 ** attempt);
    }
  }
  throw lastError;
}

/** True when an error is worth retrying (network hiccup or 5xx). */
export function isTransientError(err: unknown): boolean {
  const anyErr = err as { response?: { status?: number }; code?: string } | undefined;
  const status = anyErr?.response?.status;
  if (typeof status === "number") {
    return status >= 500 && status < 600;
  }
  // No HTTP response → network/timeout error (axios ERR_NETWORK / ECONNABORTED).
  return true;
}
