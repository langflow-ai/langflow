import { SIDEBAR_BUNDLES } from "@/utils/styleUtils";

export const BUNDLE_NAMES: readonly string[] = SIDEBAR_BUNDLES.map(
  (bundle) => bundle.name,
);

/**
 * Whether a category is listed under the sidebar's "Components" group.
 *
 * This is the rule `CategoryGroup` renders by, and the sidebar's visibility
 * checks share it: every category with items that is not a bundle,
 * `custom_component` or `MCP` is listed there. That includes categories that
 * are not in the curated `SIDEBAR_CATEGORIES` list (for example folders
 * contributed through `LANGFLOW_COMPONENTS_PATH`).
 */
export function isComponentsGroupCategory(
  categoryName: string,
  items: Record<string, unknown>,
): boolean {
  return (
    !BUNDLE_NAMES.includes(categoryName) &&
    categoryName !== "custom_component" &&
    categoryName !== "MCP" &&
    Object.keys(items).length > 0
  );
}
