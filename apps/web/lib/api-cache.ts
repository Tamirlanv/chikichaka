/**
 * In-memory GET cache for browser apiFetch to cut duplicate requests (same session tab).
 * Call bustApiCache after mutations that change server state.
 */

type Entry = { expiresAt: number; value: unknown };

const store = new Map<string, Entry>();

function cacheKey(path: string, init?: RequestInit) {
  const method = (init?.method ?? "GET").toUpperCase();
  return `${method}:${path}:${init?.body ?? ""}`;
}

export function getCached<T>(path: string, init?: RequestInit): T | undefined {
  if ((init?.method ?? "GET").toUpperCase() !== "GET") return undefined;
  const k = cacheKey(path, init);
  const hit = store.get(k);
  if (!hit || Date.now() >= hit.expiresAt) {
    if (hit) store.delete(k);
    return undefined;
  }
  return hit.value as T;
}

export function setCached<T>(path: string, value: T, ttlMs: number, init?: RequestInit): void {
  if ((init?.method ?? "GET").toUpperCase() !== "GET") return;
  const k = cacheKey(path, init);
  store.set(k, { expiresAt: Date.now() + ttlMs, value });
}

/** Invalidate entries whose key contains `needle` (e.g. "/candidates/me"). */
export function bustApiCache(needle: string) {
  for (const k of store.keys()) {
    if (k.includes(needle)) store.delete(k);
  }
}
