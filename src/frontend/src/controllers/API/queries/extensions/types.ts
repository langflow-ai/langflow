/**
 * Wire-format types for the extension reload endpoint.
 *
 * Mirrors the Python ReloadResult.to_dict() / ExtensionError.to_dict()
 * shapes from the lfx package; if the backend shape changes these need
 * to change in lockstep.  Kept in their own file so the mutation hook
 * and any UI-side consumers (toast formatters, tests) share one source
 * of truth.
 */

export interface ExtensionErrorPayload {
  code: string;
  message: string;
  hint: string;
  location: string | null;
  content: string | null;
  ref_url: string | null;
}

export interface ReloadBundleResponse {
  ok: boolean;
  bundle: string;
  reload_id: string;
  components_added: string[];
  components_removed: string[];
  /**
   * Class names present in both pre- and post-reload records whose backing
   * source file's SHA-256 changed.  Emitted by the backend so body-only
   * edits are not misreported as "no component changes".
   */
  components_changed: string[];
  errors: ExtensionErrorPayload[];
  warnings: ExtensionErrorPayload[];
}

/**
 * Body of a 409 Conflict from the reload endpoint.
 *
 * The HTTP layer wraps this in a FastAPI ``detail`` envelope; the API
 * helper unwraps it before the mutation hook surfaces it as an error.
 */
export interface ReloadInProgressDetail {
  code: "reload-in-progress";
  message: string;
  bundle: string;
}
