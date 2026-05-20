/**
 * Providers that require local infrastructure (servers, GPUs, model downloads)
 * and are incompatible with resource-constrained cloud environments.
 *
 * When cloud-only mode is active, models from these providers are hidden
 * from the unified Language Model and Embedding Model dropdowns.
 */
export const CLOUD_INCOMPATIBLE_PROVIDERS: ReadonlySet<string> = new Set([
  "Ollama",
]);
