import type { ReactNode } from "react";

export interface ConnectionsTabDefinition {
  /** Tab id, used as the `Tabs` value and in the URL query when the page syncs one. */
  value: string;
  label: string;
  /** Rendered when the tab is active. */
  render: () => ReactNode;
  /** Hides the tab without removing it from the list, e.g. for non-operators. */
  hidden?: boolean;
}

export interface ConnectionsTabsContext {
  /** True when the caller may administer instance-owned connections. */
  isOperator: boolean;
  /**
   * True when a plugin owns integration policy, from
   * `GET /integrations/policy/effective`. A tab that edits policy must render
   * read-only in that case, because the policy bundle is not the source of truth.
   */
  policyManagedExternally: boolean;
}

/**
 * Seam for extra tabs on Settings → Connections.
 *
 * OSS ships the connection tabs only; policy administration lives with the rest
 * of the catalog policy in the distribution that owns it. A distribution
 * replaces this file to append its own tabs (a Policy tab, for example) without
 * forking the page.
 */
export function CustomConnectionsTabs(
  _context: ConnectionsTabsContext,
): ConnectionsTabDefinition[] {
  return [];
}

export default CustomConnectionsTabs;
