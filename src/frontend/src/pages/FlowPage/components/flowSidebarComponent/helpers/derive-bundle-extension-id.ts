import type { APIDataType } from "@/types/api";

/**
 * Derive the extension_id for a bundle/category by inspecting the first
 * decorated template in its component map.
 *
 * Backend `_decorate_template_with_extension` stamps `extension` (the
 * extension_id) onto every component template emitted from a manifest-
 * shipping bundle.  The static `SIDEBAR_BUNDLES` list does not carry that
 * field, and dynamic categories rendered by `CategoryGroup` have no
 * SidebarBundle entry at all, so without this helper the palette has no
 * way to surface the Reload action for runtime-discovered extensions.
 *
 * Returns `undefined` when no template in the group declares an extension
 * (built-in / custom-component categories), which is the same shape the
 * static list uses to opt out of reload UI.
 */
export function deriveBundleExtensionId(
  bundleName: string,
  dataFilter: APIDataType,
): string | undefined {
  const components = dataFilter?.[bundleName];
  if (!components) return undefined;
  for (const component of Object.values(components)) {
    const candidate = (component as { extension?: unknown })?.extension;
    if (typeof candidate === "string" && candidate.length > 0) {
      return candidate;
    }
  }
  return undefined;
}
