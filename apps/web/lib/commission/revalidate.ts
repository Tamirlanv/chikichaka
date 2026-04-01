import { getUpdates } from "./query";

/**
 * Global singleton poller for commission updates.
 *
 * Only one polling loop ever runs, regardless of how many times React mounts
 * `BoardContainer` (Strict Mode double-mount, HMR, multiple tabs via
 * localStorage lease).  Subscribers register/unregister via
 * `subscribeToUpdates` / `unsubscribeFromUpdates`.
 */

type Listener = (changedApplicationIds: string[]) => void;
type UnauthorizedHandler = () => void;

const INTERVAL_MS = 15_000;
const MAX_INTERVAL_MS = 60_000;
const NET_COOLDOWN_MS = 120_000;

let _cursor: string | null = null;
let _active = false;
let _inFlight = false;
let _currentDelay = INTERVAL_MS;
let _timerId: ReturnType<typeof setTimeout> | null = null;
const _listeners = new Set<Listener>();
let _onUnauthorized: UnauthorizedHandler | null = null;

function errorStatusCode(error: unknown): number | null {
  if (!error || typeof error !== "object") return null;
  const status = (error as { status?: unknown }).status;
  return typeof status === "number" ? status : null;
}

function _scheduleNext(delayMs: number) {
  if (!_active) return;
  const normalized = Math.max(INTERVAL_MS, Math.min(delayMs, MAX_INTERVAL_MS));
  _currentDelay = normalized;
  if (_timerId !== null) clearTimeout(_timerId);
  _timerId = setTimeout(() => void _tick(), normalized);
}

async function _tick(): Promise<void> {
  if (!_active || _inFlight) return;
  if (typeof document !== "undefined" && document.visibilityState !== "visible") {
    _scheduleNext(60_000);
    return;
  }
  _inFlight = true;
  try {
    const upd = await getUpdates(_cursor);
    _cursor = upd.latestCursor;
    if (upd.changedApplicationIds.length) {
      for (const fn of _listeners) fn(upd.changedApplicationIds);
    }
    _scheduleNext(INTERVAL_MS);
  } catch (error) {
    const status = errorStatusCode(error);
    if (status === 401 || status === 403) {
      _stop();
      _onUnauthorized?.();
      return;
    }
    if (status === null) {
      _scheduleNext(NET_COOLDOWN_MS);
    } else {
      _scheduleNext(Math.min(_currentDelay * 2, MAX_INTERVAL_MS));
    }
  } finally {
    _inFlight = false;
  }
}

function _start() {
  if (_active) return;
  _active = true;
  _currentDelay = INTERVAL_MS;
  _scheduleNext(INTERVAL_MS);
}

function _stop() {
  _active = false;
  if (_timerId !== null) {
    clearTimeout(_timerId);
    _timerId = null;
  }
}

export function subscribeToUpdates(
  listener: Listener,
  opts?: { onUnauthorized?: UnauthorizedHandler },
): void {
  _listeners.add(listener);
  if (opts?.onUnauthorized) _onUnauthorized = opts.onUnauthorized;
  _start();
}

export function unsubscribeFromUpdates(listener: Listener): void {
  _listeners.delete(listener);
  if (_listeners.size === 0) _stop();
}

export function stopPolling(): void {
  _stop();
  _listeners.clear();
}

