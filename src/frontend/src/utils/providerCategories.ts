/** Provider classification helpers derived from the ``/api/v1/models``
 * payload. Source of truth lives in ``MODEL_PROVIDER_METADATA`` on the
 * backend — these helpers just inspect the metadata that already rides
 * with each provider in the API response, so adding a new credentialless
 * provider on the backend automatically flips its UI behavior here
 * (no second list to keep in sync).
 */

interface ProviderShape {
  variables?: Array<{ required?: boolean }>;
}

/** A provider is "credentialless" when none of its declared variables are
 * required — there's nothing the user has to type before models can run.
 * Mirrors the backend's ``has_required_vars`` check in
 * ``_validate_and_get_enabled_providers``.
 *
 * Treats missing/empty ``variables`` (e.g. partial responses) as
 * credentialed so we err on the side of the legacy
 * ``is_enabled || is_configured`` behavior.
 */
export const isCredentiallessProvider = (
  provider: ProviderShape | undefined | null,
): boolean => {
  const vars = provider?.variables;
  if (!Array.isArray(vars) || vars.length === 0) return false;
  return vars.every((v) => !v?.required);
};
