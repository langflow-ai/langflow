// Uniform "not ready" state for endpoints that aren't implemented yet.
//
// Contract-first: unimplemented endpoints return a structured 501 —
// `{ detail: "<human message>", status: "not_implemented" }` (see the backlog
// "Stub convention"). Every not-yet-built lothal surface renders this single
// component keyed off that shape, so they all look consistent without
// per-screen error handling. A story "goes live" by replacing its 501 body
// with a real implementation; the UI needs no change.

import type { ReactNode } from "react";
import { LothalMark } from "./LothalMark";

type NotImplementedBody = { detail?: string; status?: string };

type MaybeAxiosError = {
  response?: { status?: number; data?: NotImplementedBody };
  status?: number;
  data?: NotImplementedBody;
};

/**
 * True when an error (axios error or a raw response body) is the contract's
 * structured 501 — either an HTTP 501 or a `status: "not_implemented"` body.
 */
export function isNotImplemented(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const e = error as MaybeAxiosError;
  const status = e.response?.status ?? e.status;
  const body = e.response?.data ?? e.data;
  return status === 501 || body?.status === "not_implemented";
}

/** The human message from a structured 501, or a dockyard-flavored fallback. */
export function notImplementedDetail(
  error: unknown,
  fallback = "This part of the dockyard isn't built yet.",
): string {
  if (!error || typeof error !== "object") return fallback;
  const e = error as MaybeAxiosError;
  return e.response?.data?.detail ?? e.data?.detail ?? fallback;
}

export function NotReady({
  title = "Not ready yet",
  detail,
  error,
  action,
}: {
  title?: ReactNode;
  /** Explicit message. If omitted, derived from `error` (a structured 501). */
  detail?: ReactNode;
  /** A caught error; its 501 `detail` is shown when `detail` isn't given. */
  error?: unknown;
  action?: ReactNode;
}) {
  const message =
    detail ?? (error !== undefined ? notImplementedDetail(error) : undefined);
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 12,
        padding: 40,
        textAlign: "center",
        height: "100%",
      }}
    >
      <div style={{ color: "var(--ink-faint)" }}>
        <LothalMark size={40} />
      </div>
      <div
        className="serif"
        style={{ fontSize: 24, color: "var(--ink-mute)", fontStyle: "italic" }}
      >
        {title}
      </div>
      {message && (
        <div style={{ fontSize: 13, color: "var(--ink-soft)", maxWidth: 380 }}>
          {message}
        </div>
      )}
      {action}
    </div>
  );
}
