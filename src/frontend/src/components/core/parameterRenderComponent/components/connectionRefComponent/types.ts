import type { ConditionalScopeRequirement } from "@/utils/connection-scopes";

/**
 * Extra props a `connection_ref` field carries in its template, alongside the
 * shared `BaseInputProps`. The backend writes them from `ConnectionRefInput`
 * (see `lfx.io.ConnectionRefInput`), so the names are the wire names.
 */
export type ConnectionRefComponentType = {
  /** Provider id the field accepts, e.g. "google", "microsoft", "slack". */
  provider?: string;
  /** Scopes the action needs; a connection without all of them cannot run it. */
  requiredScopes?: string[];
  /**
   * Scopes the action needs only for some inputs, e.g. `Sites.Read.All` once a
   * SharePoint site id is set. Active ones count as required.
   */
  conditionalScopes?: ConditionalScopeRequirement[];
  /**
   * The node's current input values keyed by input name, which decide the
   * conditional scopes. Omitted, no conditional scope is active.
   */
  inputValues?: Record<string, unknown>;
  /** Capability ids this field covers, e.g. ["google.gmail.send"]. */
  capabilities?: string[];
  /** Identity the connection must execute as, e.g. "user" or "bot". */
  identityKind?: string;
  /** Ownership the field requires, independently of execution identity. */
  ownershipMode?: "user" | "instance" | "any";
};
