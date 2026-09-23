import type { ConnectionRead } from "@/controllers/API/queries/connections/use-get-connections";
import { missingScopes as uncoveredScopes } from "@/utils/connection-scopes";

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
  /** The view translates this reason using the connection and missing scopes. */
  unusableReason?: "status" | "userRequired" | "instanceRequired" | "scopes";
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

const IDENTITY_KINDS = new Map<string, "user" | "instance">([
  ["user_delegated", "user"],
  ["bot", "instance"],
  ["service", "instance"],
]);

/**
 * A field declares the identity it must run as. Bundles derive that from the
 * capability manifest with `{user_delegated: "user", bot: "instance", service:
 * "instance"}` (see `lfx_microsoft.manifest`), so the picker maps a connection
 * the same way rather than inventing a second vocabulary. A connection that
 * does not say who it runs as has no kind: it is unknown, not the instance.
 */
export function identityKindOf(
  connection: ConnectionRead,
): "user" | "instance" | undefined {
  const identity = connection.executing_identity?.identity;
  return identity ? IDENTITY_KINDS.get(identity) : undefined;
}

export function identityMatches(
  connection: ConnectionRead,
  identityKind: string | undefined,
): boolean {
  if (!identityKind || identityKind === "any") return true;
  const kind = identityKindOf(connection);
  // Only flag a mismatch the picker can see; the run-time check still refuses
  // a connection whose identity turns out to be wrong.
  return kind === undefined || kind === identityKind;
}

/**
 * Required scopes the connection has not been granted, compared the way the
 * backend compares them (`ScopeSet.missing`): Google and Microsoft scopes match
 * with or without their URL prefix, and case does not matter.
 */
export function missingScopesFor(
  connection: ConnectionRead,
  requiredScopes: string[],
): string[] {
  return uncoveredScopes(
    connection.provider_key,
    requiredScopes,
    connection.granted_scopes ?? [],
  );
}

function unusableReason(
  connection: ConnectionRead,
  missingScopes: string[],
  identityKind: string | undefined,
): ConnectionOption["unusableReason"] {
  if (connection.status !== "ready") return "status";
  if (!identityMatches(connection, identityKind)) {
    return identityKind === "user" ? "userRequired" : "instanceRequired";
  }
  if (missingScopes.length) return "scopes";
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
  identityKind?: string,
): ConnectionOption[] {
  return connections
    .map((connection) => {
      const missingScopes = missingScopesFor(connection, requiredScopes);
      const reason = unusableReason(connection, missingScopes, identityKind);
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
