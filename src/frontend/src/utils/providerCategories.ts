/** Providers whose models run locally inside the langflow process and have
 * no required credential variable. Treated specially by the UI:
 *
 * - The model provider list/item considers them "active" only when at least
 *   one of their models is enabled — ``is_configured`` is True for free
 *   (no credential to satisfy), so the usual ``is_enabled || is_configured``
 *   fallback would make them look permanently activated.
 * - The Assistant's model picker hides them entirely until it learns to
 *   route through local-inference adapters.
 *
 * Add new entries as more credentialless providers ship.
 */
export const CREDENTIALLESS_PROVIDERS: ReadonlySet<string> = new Set([
  "HuggingFace",
]);

export const isCredentiallessProvider = (provider: string): boolean =>
  CREDENTIALLESS_PROVIDERS.has(provider);
