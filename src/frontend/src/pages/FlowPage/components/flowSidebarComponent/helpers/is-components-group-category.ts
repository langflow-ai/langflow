/**
 * Whether a category is listed under the sidebar's "Components" group.
 *
 * Mirrors the filter used by `CategoryGroup`: every category with items that is
 * not a bundle, `custom_component` or `MCP` is rendered there. That includes
 * categories that are not in the curated `SIDEBAR_CATEGORIES` list (for example
 * folders contributed through `LANGFLOW_COMPONENTS_PATH`).
 */
export function isComponentsGroupCategory(
  categoryName: string,
  items: Record<string, unknown>,
  bundleNames: readonly string[],
): boolean {
  return (
    !bundleNames.includes(categoryName) &&
    categoryName !== "custom_component" &&
    categoryName !== "MCP" &&
    Object.keys(items).length > 0
  );
}
