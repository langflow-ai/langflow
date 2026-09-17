import type { ConnectionRead } from "@/controllers/API/queries/connections/use-get-connections";

/**
 * A connection as the picker offers it: the stored handle, why it cannot be
 * used yet, and the scopes it is missing for this field.
 */
export type ConnectionOption = {
  /** Portable handle stored in the flow, e.g. "google/work". */
  handle: string;
  connection: ConnectionRead;
  /** Required scopes this connection has not been granted. */
  missingScopes: string[];
  /** True when the connection is ready and covers every required scope. */
  usable: boolean;
  /** Short reason shown next to an unusable option. */
  unusableReason?: string;
};

/**
 * Providers publish scopes in their own form: Google and Microsoft use absolute
 * URLs, Slack uses bare names. Show the last path segment so a list of scopes
 * stays readable, and never let it collapse to an empty string.
 */
export function shortScope(scope: string): string {
  const trimmed = scope.trim().replace(/\/+$/, "");
  if (!trimmed.includes("://")) return trimmed;
  const tail = trimmed.split("/").pop();
  return tail || trimmed;
}

/** The handle a flow stores for a connection; the backend resolves it at run time. */
export function connectionHandle(connection: ConnectionRead): string {
  return `${connection.provider_key}/${connection.name}`;
}

export function missingScopesFor(
  connection: ConnectionRead,
  requiredScopes: string[],
): string[] {
  const granted = new Set(connection.granted_scopes ?? []);
  return requiredScopes.filter((scope) => !granted.has(scope));
}

function unusableReason(
  connection: ConnectionRead,
  missingScopes: string[],
): string | undefined {
  if (connection.status !== "ready")
    return `Connection is ${connection.status}`;
  if (missingScopes.length)
    return `Missing ${missingScopes.map(shortScope).join(", ")}`;
  return undefined;
}

/**
 * Builds the picker's options. Every connection for the provider is listed,
 * including ones that cannot run this action, so the reason is visible instead
 * of the connection silently missing. Usable options come first, then the most
 * recently updated.
 */
export function buildConnectionOptions(
  connections: ConnectionRead[],
  requiredScopes: string[] = [],
): ConnectionOption[] {
  return connections
    .map((connection) => {
      const missingScopes = missingScopesFor(connection, requiredScopes);
      const reason = unusableReason(connection, missingScopes);
      return {
        handle: connectionHandle(connection),
        connection,
        missingScopes,
        usable: reason === undefined,
        unusableReason: reason,
      };
    })
    .sort((left, right) => {
      if (left.usable !== right.usable) return left.usable ? -1 : 1;
      return String(right.connection.updated_at).localeCompare(
        String(left.connection.updated_at),
      );
    });
}

/** Describes the connected account for the option's second line. */
export function accountLabel(connection: ConnectionRead): string {
  const account = connection.executing_identity?.account;
  return account?.display || account?.id || connection.display_name;
}
