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
  /** Capability ids this field covers, e.g. ["google.gmail.send"]. */
  capabilities?: string[];
  /** Identity the connection must execute as, e.g. "user" or "bot". */
  identityKind?: string;
};
