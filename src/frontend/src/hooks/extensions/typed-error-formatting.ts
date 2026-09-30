/**
 * Shared formatting helpers for ExtensionError payloads emitted by the
 * reload pipeline.
 *
 * Both the click-initiated path (``bundleHeaderActions.tsx`` onSuccess) and
 * the polled-event path (``use-extension-events.ts`` bundle_reloaded handler)
 * need to render the same ``warnings`` / ``errors`` list into an alert-store
 * shape. Keeping the renderer in one module prevents the two paths from
 * drifting -- the original divergence (clicking tab surfaced warnings,
 * mirrored-event tabs did not) was the symptom of having the renderer
 * inlined in only one of them.
 */

import type { ExtensionErrorPayload } from "@/controllers/API/queries/extensions";

export type TypedErrorAlertList = { title: string; list: string[] } | undefined;

/**
 * Render a list of typed errors / warnings into the alert-store list shape.
 *
 * The UI shows the first sentence (code + message) plus the hint indented;
 * keeping the hint in the same alert means the user does not need to dig
 * for the fix when a reload fails. Returns ``undefined`` when the input
 * list is empty so the alert store does not render an empty bullet list.
 */
export function renderTypedErrorList(
  payloads: readonly ExtensionErrorPayload[],
): TypedErrorAlertList {
  if (payloads.length === 0) {
    return undefined;
  }
  const list = payloads.flatMap((p) => {
    const lines: string[] = [`[${p.code}] ${p.message}`];
    if (p.hint) {
      lines.push(`  ${p.hint}`);
    }
    return lines;
  });
  return { title: "Reload diagnostics", list };
}

/**
 * Coerce an unknown bus-payload field into a ``ExtensionErrorPayload[]``.
 *
 * Event payloads in ``use-extension-events`` are typed as
 * ``Record<string, unknown>`` because the backend ships them as opaque JSON
 * dicts. ``warnings`` and ``errors`` on a ``bundle_reloaded`` /
 * ``bundle_reload_failed`` event match ``ExtensionErrorPayload`` in shape;
 * this helper does the minimal narrowing (must be an array of objects with
 * a string ``code`` and ``message``) so a malformed payload from an older
 * server cannot crash the toast pipeline.
 */
export function extractTypedErrorList(
  value: unknown,
): readonly ExtensionErrorPayload[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((entry): entry is ExtensionErrorPayload => {
    if (entry === null || typeof entry !== "object") {
      return false;
    }
    const candidate = entry as Record<string, unknown>;
    return (
      typeof candidate.code === "string" &&
      typeof candidate.message === "string"
    );
  });
}
