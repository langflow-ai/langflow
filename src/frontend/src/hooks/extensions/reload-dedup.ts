const RECENT_OWN_RELOADS = new Map<string, number>();
const DEDUP_TTL_MS = 30_000;

function sweepExpired(now: number): void {
  for (const [id, expiresAt] of RECENT_OWN_RELOADS) {
    if (expiresAt <= now) RECENT_OWN_RELOADS.delete(id);
  }
}

export function markOwnReload(reloadId: string | undefined | null): void {
  if (typeof reloadId !== "string" || reloadId.length === 0) return;
  const now = Date.now();
  RECENT_OWN_RELOADS.set(reloadId, now + DEDUP_TTL_MS);
  sweepExpired(now);
}

export function isOwnReload(reloadId: unknown): boolean {
  if (typeof reloadId !== "string") return false;
  const expiresAt = RECENT_OWN_RELOADS.get(reloadId);
  if (expiresAt === undefined) return false;
  if (expiresAt <= Date.now()) {
    RECENT_OWN_RELOADS.delete(reloadId);
    return false;
  }
  return true;
}

export function _resetOwnReloadDedup(): void {
  RECENT_OWN_RELOADS.clear();
}
