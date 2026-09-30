/**
 * LE-2037: node parameter fields derive their id from the template type/name
 * alone, so two nodes exposing the same field render duplicate DOM ids — a
 * WCAG 4.1.1 violation that also stops browser autofill from working.
 *
 * Scoping the DOM id by node makes it unique without touching the base id,
 * which is what `data-testid` is built from and what the e2e suite selects on.
 */
export function getNodeScopedDomId(
  id?: string,
  nodeId?: string,
): string | undefined {
  if (!id) return id;
  return nodeId ? `${id}-${nodeId}` : id;
}
