/** Read the optional ``display_name`` slug stored on a model's metadata.
 *
 * Catalogs (e.g. ``HUGGINGFACE_MODELS_DETAILED``) ship a short Ollama-style
 * slug alongside the canonical model id; the slug is what we want to render
 * in dropdown triggers and toggles when present, falling back to the
 * canonical id for legacy catalogs without the field.
 */
export function readModelDisplayName(
  metadata: Record<string, unknown> | undefined | null,
): string | undefined {
  const value = metadata?.display_name;
  return typeof value === "string" && value ? value : undefined;
}
