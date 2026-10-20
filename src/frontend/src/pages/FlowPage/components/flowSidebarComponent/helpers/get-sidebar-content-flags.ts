import {
  BUNDLE_NAMES,
  isComponentsGroupCategory,
} from "./is-components-group-category";

/**
 * Which sidebar sections have anything to show for the (filtered) component
 * data. `hasResults` is true when any section does.
 */
export function getSidebarContentFlags(
  dataFilter: Record<string, Record<string, unknown>>,
) {
  const hasCoreComponents = Object.entries(dataFilter).some(
    ([category, items]) => isComponentsGroupCategory(category, items),
  );
  const hasBundleItems = BUNDLE_NAMES.some(
    (name) => dataFilter[name] && Object.keys(dataFilter[name]).length > 0,
  );
  const hasMcpComponents = Boolean(
    dataFilter["MCP"] && Object.keys(dataFilter["MCP"]).length > 0,
  );

  return {
    hasCoreComponents,
    hasBundleItems,
    hasMcpComponents,
    hasResults: hasCoreComponents || hasBundleItems || hasMcpComponents,
  };
}
